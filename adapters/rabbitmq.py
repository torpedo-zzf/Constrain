"""RabbitMQ connection management adapter.

Provides a connection pool and channel management for the RabbitMQEventBus.
Re-exported from core/event_bus/backends/rabbitmq.py for convenience.
"""

from core.event_bus.backends.rabbitmq import RabbitMQEventBus

__all__ = ["RabbitMQEventBus"]
