from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from core.event_bus.base import EventBus
from core.event_bus.models import Event

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]


class RabbitMQEventBus(EventBus):
    """RabbitMQ-backed event bus.

    Requires aio-pika. Uses:
    - Direct exchanges for point-to-point task dispatch.
    - Fanout exchanges for event broadcast.
    - Fair dispatch with basicQos=1 and manual ACK.
    """

    def __init__(self, url: str = "amqp://guest:guest@localhost:5672/") -> None:
        self._url = url
        self._connection: Any = None
        self._channel: Any = None
        self._exchange: Any = None
        self._dead_letter_exchange: Any = None

    async def _ensure_connection(self) -> None:
        if self._channel is not None:
            return
        try:
            import aio_pika
        except ImportError:
            raise ImportError("aio-pika is required for RabbitMQEventBus")
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)
        self._exchange = await self._channel.declare_exchange(
            "constrain.direct", aio_pika.ExchangeType.DIRECT, durable=True
        )
        self._dead_letter_exchange = await self._channel.declare_exchange(
            "constrain.dlx", aio_pika.ExchangeType.FANOUT, durable=True
        )

    async def publish(self, event: Event, routing_key: str) -> None:
        await self._ensure_connection()
        import aio_pika

        message = aio_pika.Message(
            body=json.dumps(event.model_dump()).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=event.event_id,
            type=event.event_type,
        )
        await self._exchange.publish(message, routing_key=routing_key)

    async def subscribe(
        self, event_type: str, handler: EventHandler, consumer_tag: str
    ) -> None:
        await self._ensure_connection()
        queue = await self._channel.declare_queue(
            f"constrain.{event_type}", durable=True
        )
        await queue.bind(self._exchange, routing_key=event_type)

        async def on_message(message: Any) -> None:
            async with message.process(requeue=True):
                body = json.loads(message.body.decode())
                event = Event(**body)
                try:
                    await handler(event)
                except Exception:
                    logger.exception("Handler failed for event %s", event.event_id)
                    raise

        await queue.consume(on_message, consumer_tag=consumer_tag)

    async def ack(self, event_id: str) -> None:
        pass  # Handled via message.process() context manager

    async def nack(self, event_id: str, requeue: bool = True) -> None:
        pass  # Handled via message.process() context manager

    async def start(self) -> None:
        await self._ensure_connection()

    async def stop(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None
            self._channel = None
