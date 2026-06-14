from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from core.event_bus.base import EventBus
from core.event_bus.models import Event

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]


class MemoryEventBus(EventBus):
    """In-memory event bus using asyncio primitives.

    Intended for single-process development and testing.
    All events are delivered synchronously via an in-process queue.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, dict[str, EventHandler]] = defaultdict(dict)
        self._dead_letter: list[Event] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._pending_acks: set[str] = set()
        self._max_retries: int = 3

    async def publish(self, event: Event, routing_key: str = "") -> None:
        logger.debug("Publishing event | type=%s id=%s", event.event_type, event.event_id)
        await self._queue.put(event)

    async def subscribe(
        self, event_type: str, handler: EventHandler, consumer_tag: str
    ) -> None:
        self._handlers[event_type][consumer_tag] = handler
        logger.debug(
            "Subscribed | type=%s tag=%s", event_type, consumer_tag
        )

    async def unsubscribe(self, consumer_tag: str) -> None:
        for handlers in self._handlers.values():
            handlers.pop(consumer_tag, None)

    async def ack(self, event_id: str) -> None:
        self._pending_acks.discard(event_id)

    async def nack(self, event_id: str, requeue: bool = True) -> None:
        self._pending_acks.discard(event_id)
        logger.warning("NACK | event_id=%s requeue=%s", event_id, requeue)

    async def _deliver(self, event: Event) -> None:
        handlers = self._handlers.get(event.event_type, {})
        if not handlers:
            logger.debug("No handlers for event type=%s", event.event_type)
            return

        for consumer_tag, handler in list(handlers.items()):
            retries = 0
            while retries <= self._max_retries:
                try:
                    await handler(event)
                    break
                except Exception:
                    retries += 1
                    if retries > self._max_retries:
                        logger.exception(
                            "Handler failed after %d retries | type=%s tag=%s event_id=%s",
                            self._max_retries,
                            event.event_type,
                            consumer_tag,
                            event.event_id,
                        )
                        self._dead_letter.append(event)
                    else:
                        await asyncio.sleep(0.5 * retries)

    async def start(self) -> None:
        if self._worker_task is not None:
            return
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task is not None:
            # Signal the worker to stop after draining pending events
            await self._queue.put(None)  # sentinel
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def _worker_loop(self) -> None:
        while True:
            try:
                event = await self._queue.get()
                if event is None:  # sentinel — time to stop
                    self._queue.task_done()
                    break
                await self._deliver(event)
                self._queue.task_done()
            except Exception:
                logger.exception("Unexpected error in event bus worker")
