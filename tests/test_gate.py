import pytest

from core.gate import GateLayer, GatePipeline, GateVerdict, RuleResult


async def pass_rule(content):
    return RuleResult(rule_name="pass_rule", verdict=GateVerdict.PASS, reason="ok")


async def reject_rule(content):
    return RuleResult(rule_name="reject_rule", verdict=GateVerdict.REJECT, reason="bad content")


async def need_review_rule(content):
    return RuleResult(rule_name="review_rule", verdict=GateVerdict.NEED_REVIEW, reason="needs human")


@pytest.mark.asyncio
async def test_layer_all_pass():
    layer = GateLayer("test", combine="and")
    layer.add_rule(pass_rule)
    layer.add_rule(pass_rule)

    result = await layer.evaluate({"data": "test"})
    assert result.verdict == GateVerdict.PASS


@pytest.mark.asyncio
async def test_layer_any_reject():
    layer = GateLayer("test", combine="and")
    layer.add_rule(pass_rule)
    layer.add_rule(reject_rule)

    result = await layer.evaluate({"data": "test"})
    assert result.verdict == GateVerdict.REJECT


@pytest.mark.asyncio
async def test_layer_or_combine():
    layer = GateLayer("test", combine="or")
    layer.add_rule(pass_rule)
    layer.add_rule(reject_rule)

    result = await layer.evaluate({"data": "test"})
    assert result.verdict == GateVerdict.PASS


@pytest.mark.asyncio
async def test_pipeline_l1_reject_stops():
    pipeline = GatePipeline()
    l1 = GateLayer("L1", combine="and")
    l1.add_rule(reject_rule)
    pipeline.add_layer(l1)

    result = await pipeline.evaluate({"data": "test"})
    assert result.verdict == GateVerdict.REJECT
    assert result.layer_name == "L1"


@pytest.mark.asyncio
async def test_pipeline_l2_escalates():
    pipeline = GatePipeline(l2_confidence_threshold=0.5)
    l1 = GateLayer("L1", combine="and")
    l1.add_rule(pass_rule)

    l2 = GateLayer("L2", combine="and")
    l2.add_rule(reject_rule)

    pipeline.add_layer(l1)
    pipeline.add_layer(l2)

    result = await pipeline.evaluate({"data": "test"})
    assert result.verdict == GateVerdict.NEED_REVIEW
