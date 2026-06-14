from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventHeaders(BaseModel):
    """Standard headers carried by every event."""

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str | None = None
    source: str | None = None
    content_type: str = "application/json"
    schema_version: str = "1.0"

    model_config = {"frozen": True, "extra": "forbid"}


class Event(BaseModel):
    """Universal event envelope for the entire framework.

    Every component communicates through Events on the EventBus.
    """

    headers: EventHeaders
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True, "extra": "forbid"}

    @classmethod
    def create(
        cls,
        event_type: str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
        source: str | None = None,
    ) -> "Event":
        return cls(
            headers=EventHeaders(
                event_type=event_type,
                trace_id=trace_id,
                source=source,
            ),
            payload=payload or {},
        )

    @property
    def event_id(self) -> str:
        return self.headers.event_id

    @property
    def event_type(self) -> str:
        return self.headers.event_type

    @property
    def trace_id(self) -> str | None:
        return self.headers.trace_id
