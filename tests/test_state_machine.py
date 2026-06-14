import pytest

from core.state_machine import StateMachine, TransitionError


@pytest.fixture
def sm():
    return StateMachine()


@pytest.mark.asyncio
async def test_create_instance(sm: StateMachine):
    await sm.create_instance("test", "entity-1")
    state = await sm.get_current_state("entity-1")
    assert state.current_state == "PENDING"
    assert state.entity_id == "entity-1"


@pytest.mark.asyncio
async def test_valid_transition(sm: StateMachine):
    await sm.create_instance("test", "e1")
    await sm.transition("e1", "RUNNING")
    state = await sm.get_current_state("e1")
    assert state.current_state == "RUNNING"


@pytest.mark.asyncio
async def test_invalid_transition(sm: StateMachine):
    await sm.create_instance("test", "e1")
    with pytest.raises(TransitionError):
        await sm.transition("e1", "SUCCEEDED")


@pytest.mark.asyncio
async def test_pause_and_resume(sm: StateMachine):
    await sm.create_instance("test", "e1")
    await sm.transition("e1", "RUNNING")
    await sm.pause("e1", "pausing for review")
    state = await sm.get_current_state("e1")
    assert state.current_state == "PAUSED"
    assert "reason" in state.context

    await sm.resume("e1")
    state = await sm.get_current_state("e1")
    assert state.current_state == "RUNNING"


@pytest.mark.asyncio
async def test_event_sourcing(sm: StateMachine):
    await sm.create_instance("test", "entity-es")
    await sm.transition("entity-es", "RUNNING")

    hist = await sm.get_state_history("entity-es")
    assert len(hist) == 2
    assert hist[0].to_state == "PENDING"
    assert hist[1].to_state == "RUNNING"
