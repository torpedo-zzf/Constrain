from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from core.gate.models import GateResult, GateVerdict, RuleResult

logger = logging.getLogger(__name__)

RuleFn = Callable[[dict[str, Any]], Coroutine[Any, Any, RuleResult]]


class GateLayer:
    """A single layer in the gate pipeline, containing one or more rules.

    Rules within a layer are combined using AND/OR logic.
    """

    def __init__(self, name: str, combine: str = "and") -> None:
        if combine not in ("and", "or"):
            raise ValueError(f"combine must be 'and' or 'or', got {combine}")
        self.name = name
        self._combine = combine
        self._rules: list[RuleFn] = []

    def add_rule(self, rule: RuleFn) -> None:
        self._rules.append(rule)

    async def evaluate(self, content: dict[str, Any]) -> GateResult:
        results: list[RuleResult] = []
        for rule in self._rules:
            result = await rule(content)
            results.append(result)

        if self._combine == "and":
            verdict = GateVerdict.PASS
            if any(r.verdict == GateVerdict.REJECT for r in results):
                verdict = GateVerdict.REJECT
            elif any(r.verdict == GateVerdict.NEED_REVIEW for r in results):
                verdict = GateVerdict.NEED_REVIEW
        else:
            verdict = GateVerdict.REJECT
            if any(r.verdict == GateVerdict.PASS for r in results):
                verdict = GateVerdict.PASS
            elif any(r.verdict == GateVerdict.NEED_REVIEW for r in results):
                verdict = GateVerdict.NEED_REVIEW

        return GateResult(layer_name=self.name, verdict=verdict, rule_results=results)


class GatePipeline:
    """Layered quality gate pipeline.

    L1: Hard compliance — automatic rejection on failure.
    L2: Technical standards — configurable threshold, can escalate to review.
    L3: Creative evaluation — human-in-the-loop review.
    """

    def __init__(self, l2_confidence_threshold: float = 0.8) -> None:
        self._layers: list[GateLayer] = []
        self._l2_confidence_threshold = l2_confidence_threshold
        self._review_callback: Callable[[GateResult], Coroutine[Any, Any, GateResult]] | None = None
        self._audit_log: list[dict[str, Any]] = []

    def add_layer(self, layer: GateLayer) -> None:
        """Register a gate layer in order (e.g., L1, L2, L3)."""
        self._layers.append(layer)

    def on_review_required(self, callback: Callable[[GateResult], Coroutine[Any, Any, GateResult]]) -> None:
        """Register a callback for L3 human-in-the-loop review resolution."""
        self._review_callback = callback

    async def evaluate(self, content: dict[str, Any]) -> GateResult:
        """Run content through all registered gate layers.

        Processing stops at the first REJECT.

        Args:
            content: The content dict to evaluate (e.g., task output).

        Returns:
            The aggregated gate result.
        """
        overall_verdict = GateVerdict.PASS
        final_result: GateResult | None = None

        for i, layer in enumerate(self._layers):
            result = await layer.evaluate(content)

            self._audit({
                "layer": layer.name,
                "verdict": result.verdict.value,
                "confidence": result.confidence,
                "rule_count": len(result.rule_results),
            })

            # L1: Hard reject
            if i == 0 and result.verdict == GateVerdict.REJECT:
                logger.warning("L1 gate rejected content in layer %s", layer.name)
                return result

            # L2: Configurable threshold — REJECT above threshold becomes NEED_REVIEW
            if i == 1 and result.verdict == GateVerdict.REJECT:
                if result.confidence >= self._l2_confidence_threshold:
                    result.verdict = GateVerdict.NEED_REVIEW
                    logger.info("L2 threshold exceeded: REJECT escalated to NEED_REVIEW")

            # L3: Human review
            if i == 2 and result.verdict == GateVerdict.NEED_REVIEW and self._review_callback:
                logger.info("L3 gate: awaiting human review for layer %s", layer.name)
                result = await self._review_callback(result)

            if result.verdict == GateVerdict.REJECT:
                return result

            if result.verdict != GateVerdict.PASS:
                overall_verdict = result.verdict

            final_result = result

        return GateResult(
            layer_name=final_result.layer_name if final_result else "gate_pipeline",
            verdict=final_result.verdict if final_result else GateVerdict.PASS,
        )

    def get_audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)

    def _audit(self, entry: dict[str, Any]) -> None:
        self._audit_log.append(entry)
