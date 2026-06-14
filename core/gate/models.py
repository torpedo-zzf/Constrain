from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GateVerdict(str, Enum):
    PASS = "pass"
    REJECT = "reject"
    NEED_REVIEW = "need_review"


class RuleResult(BaseModel):
    """Result from a single gate rule evaluation."""
    rule_name: str
    verdict: GateVerdict
    reason: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class GateResult(BaseModel):
    """Aggregated result from a gate pipeline evaluation."""
    layer_name: str
    verdict: GateVerdict
    rule_results: list[RuleResult] = Field(default_factory=list)
    confidence: float = 1.0
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewer: str | None = None
    feedback: str | None = None

    @property
    def passed(self) -> bool:
        return self.verdict == GateVerdict.PASS

    @property
    def needs_review(self) -> bool:
        return self.verdict == GateVerdict.NEED_REVIEW
