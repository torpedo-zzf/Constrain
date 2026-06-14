import pytest

from core.arbiter import Arbiter
from core.arbiter.models import Task


@pytest.mark.asyncio
async def test_acquire_release_lock():
    arbiter = Arbiter()
    result = await arbiter.acquire_lock("resource-1", "worker-1", ttl=30)
    assert result.status.value == "acquired"

    # Second attempt should be denied
    result2 = await arbiter.acquire_lock("resource-1", "worker-2", ttl=30)
    assert result2.status.value == "denied"

    # Release
    released = await arbiter.release_lock("resource-1", "worker-1")
    assert released is True


@pytest.mark.asyncio
async def test_retry_decision():
    arbiter = Arbiter()
    task = Task(task_id="t1", skill_name="test", retry_count=1, max_retries=3)
    decision = await arbiter.decide_retry(task, ValueError("oops"))
    assert decision.should_retry is True
    assert decision.attempt == 2


@pytest.mark.asyncio
async def test_max_retries_exceeded():
    arbiter = Arbiter()
    task = Task(task_id="t1", skill_name="test", retry_count=3, max_retries=3)
    decision = await arbiter.decide_retry(task, ValueError("oops"))
    assert decision.should_retry is False


@pytest.mark.asyncio
async def test_priority_policy():
    arbiter = Arbiter()
    result = await arbiter.evaluate_policy("priority", {"priority": "urgent"})
    assert result.allowed is True

    result = await arbiter.evaluate_policy("priority", {"priority": "low", "min_priority": "high"})
    assert result.allowed is False


@pytest.mark.asyncio
async def test_audit_log():
    arbiter = Arbiter()
    await arbiter.acquire_lock("r1", "w1")
    await arbiter.evaluate_policy("priority", {"priority": "normal"})

    log = arbiter.get_audit_log()
    assert len(log) == 2
    assert log[0].action == "acquire_lock"
    assert log[1].action == "evaluate_policy"
