import pytest

from core.event_bus import Event, EventBus
from core.event_bus.backends import MemoryEventBus


@pytest.fixture
def bus():
    return MemoryEventBus()


@pytest.mark.asyncio
async def test_publish_and_subscribe(bus: MemoryEventBus):
    received = []

    async def handler(event: Event):
        received.append(event)

    await bus.subscribe("TestEvent", handler, "test-consumer")
    await bus.start()

    event = Event.create("TestEvent", {"key": "value"})
    await bus.publish(event, "test")
    await bus.stop()

    assert len(received) == 1
    assert received[0].event_type == "TestEvent"
    assert received[0].payload == {"key": "value"}


@pytest.mark.asyncio
async def test_multiple_subscribers(bus: MemoryEventBus):
    received_1 = []
    received_2 = []

    async def handler_1(e):
        received_1.append(e)

    async def handler_2(e):
        received_2.append(e)

    await bus.subscribe("MultiEvent", handler_1, "c1")
    await bus.subscribe("MultiEvent", handler_2, "c2")
    await bus.start()

    event = Event.create("MultiEvent", {"n": 1})
    await bus.publish(event, "multi")
    await bus.stop()

    assert len(received_1) == 1
    assert len(received_2) == 1


@pytest.mark.asyncio
async def test_unsubscribe(bus: MemoryEventBus):
    received = []

    async def handler(e):
        received.append(e)

    await bus.subscribe("Test", handler, "to-remove")
    await bus.unsubscribe("to-remove")
    await bus.start()

    await bus.publish(Event.create("Test", {}), "t")
    await bus.stop()

    assert len(received) == 0
