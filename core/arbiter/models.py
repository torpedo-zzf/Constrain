from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class LockStatus(str, Enum):
    ACQUIRED = "acquired"
    DENIED = "denied"
    EXPIRED = "expired"
    RELEASED = "released"


class LockResult(BaseModel):
    """Result of a distributed lock operation."""

    resource_id: str
    requester_id: str
    status: LockStatus
    ttl: int
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""


class RetryDecision(BaseModel):
    """Decision about whether and when to retry a failed task."""

    should_retry: bool
    delay_seconds: float = 0.0
    attempt: int = 0
    reason: str = ""


class PolicyResult(BaseModel):
    """Result of a policy evaluation."""

    policy_name: str
    allowed: bool
    reason: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    """Minimal task representation used by the Arbiter for decisions."""

    task_id: str
    skill_name: str
    priority: str = "normal"
    retry_count: int = 0
    max_retries: int = 3


class AuditRecord(BaseModel):
    """Immutable audit trail entry for every Arbiter decision."""

    record_id: str = Field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    requester: str
    resource: str
    decision: str
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
