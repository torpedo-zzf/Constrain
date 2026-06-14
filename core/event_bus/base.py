from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from core.event_bus.models import Event

EventHandler = Callable[[Event], Awaitable[None]]


class Publisher(ABC):
    """Abstract publisher interface — publishes events to the bus."""

    @abstractmethod
    async def publish(self, event: Event, routing_key: str) -> None: ...


class Subscriber(ABC):
    """Abstract subscriber interface — subscribes to event types."""

    @abstractmethod
    async def subscribe(
        self, event_type: str, handler: EventHandler, consumer_tag: str
    ) -> None: ...

    @abstractmethod
    async def unsubscribe(self, consumer_tag: str) -> None: ...


class EventBus(ABC):
    """Unified event bus abstraction.

    Supports two messaging patterns:
    - Point-to-point (task dispatch) via routing keys.
    - Publish-subscribe (event broadcast) via event type subscriptions.
    """

    @abstractmethod
    async def publish(self, event: Event, routing_key: str) -> None:
        """Publish an event to the bus.

        Args:
            event: The event envelope to publish.
            routing_key: Routing key for point-to-point dispatch.
        """

    @abstractmethod
    async def subscribe(
        self, event_type: str, handler: EventHandler, consumer_tag: str
    ) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: Event type string to match (e.g. "TaskStarted").
            handler: Async callable receiving the Event.
            consumer_tag: Unique consumer identifier for this subscription.
        """

    @abstractmethod
    async def ack(self, event_id: str) -> None:
        """Acknowledge successful processing of an event."""

    @abstractmethod
    async def nack(self, event_id: str, requeue: bool = True) -> None:
        """Reject an event, optionally re-queueing it for retry.

        Args:
            event_id: The event identifier to reject.
            requeue: Whether to re-queue the event for another consumer.
        """

    @abstractmethod
    async def start(self) -> None:
        """Start consuming messages (no-op for memory backend)."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shut down all consumers."""
