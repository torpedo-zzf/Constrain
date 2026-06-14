from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from core.event_bus.base import EventBus
from core.event_bus.models import Event

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]


class RedisPubSubEventBus(EventBus):
    """Redis Pub/Sub-backed event bus.

    Uses Redis channels for event broadcast.
    Point-to-point dispatch uses Redis lists (LPUSH/BRPOP).
    """

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        self._url = url
        self._redis: Any = None
        self._pubsub: Any = None

    async def _ensure_connection(self) -> None:
        if self._redis is not None:
            return
        try:
            from redis.asyncio import Redis
        except ImportError:
            raise ImportError("redis is required for RedisPubSubEventBus")
        self._redis = Redis.from_url(self._url, decode_responses=True)
        self._pubsub = self._redis.pubsub()

    async def publish(self, event: Event, routing_key: str) -> None:
        await self._ensure_connection()
        body = json.dumps(event.model_dump())
        if routing_key:
            await self._redis.rpush(f"queue:{routing_key}", body)
        else:
            await self._redis.publish(f"event:{event.event_type}", body)

    async def subscribe(
        self, event_type: str, handler: EventHandler, consumer_tag: str
    ) -> None:
        await self._ensure_connection()
        channel = f"event:{event_type}"
        await self._pubsub.subscribe(channel)

        async def listener() -> None:
            while True:
                message = await self._pubsub.get_message(
                    timeout=1.0, ignore_subscribe_messages=True
                )
                if message is None:
                    continue
                try:
                    event = Event(**json.loads(message["data"]))
                    await handler(event)
                except Exception:
                    logger.exception(
                        "Handler failed for event type=%s", event_type
                    )

        import asyncio

        asyncio.ensure_future(listener())

    async def ack(self, event_id: str) -> None:
        pass

    async def nack(self, event_id: str, requeue: bool = True) -> None:
        pass

    async def start(self) -> None:
        await self._ensure_connection()

    async def stop(self) -> None:
        if self._pubsub:
            await self._pubsub.unsubscribe()
        if self._redis:
            await self._redis.aclose()
            self._redis = None
