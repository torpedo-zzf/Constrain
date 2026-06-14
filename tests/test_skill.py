import pytest

from skill import BaseSkill, idempotent


class CountingSkill(BaseSkill):
    name = "test_skill"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self.call_count = 0

    @idempotent(ttl=60)
    async def execute(self, input_data, parameters, trace_id):
        self.call_count += 1
        return {"result": f"processed {input_data.get('key', 'unknown')}"}


@pytest.mark.asyncio
async def test_idempotency():
    skill = CountingSkill()
    result1 = await skill.execute({"key": "value"}, {}, "trace-1")
    result2 = await skill.execute({"key": "value"}, {}, "trace-2")

    assert result1 == result2
    assert skill.call_count == 1


@pytest.mark.asyncio
async def test_idempotency_different_inputs():
    skill = CountingSkill()
    result1 = await skill.execute({"key": "value1"}, {}, "trace-1")
    result2 = await skill.execute({"key": "value2"}, {}, "trace-2")

    assert result1 != result2
    assert skill.call_count == 2


def test_skill_metadata():
    skill = CountingSkill()
    assert skill.name == "test_skill"
    assert skill.version == "1.0.0"
    assert skill.validate_input({"key": "value"}) is True
