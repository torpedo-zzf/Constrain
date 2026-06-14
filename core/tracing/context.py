from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceContext:
    """W3C Trace Context compatible tracing context.

    Framework-internal representation that can convert to/from
    OpenTelemetry SpanContext for production use.

    Attributes:
        trace_id: 32-character hex string.
        span_id: 16-character hex string.
        parent_span_id: 16-character hex string or None.
        tracestate: Optional W3C tracestate string.
    """

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: str | None = None
    tracestate: str | None = None

    def new_child(self) -> "TraceContext":
        """Create a child span context sharing the same trace_id."""
        return TraceContext(
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
            tracestate=self.tracestate,
        )

    def to_otel_dict(self) -> dict[str, str]:
        """Serialize to a dict for W3C Trace Context propagation."""
        result: dict[str, str] = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }
        if self.parent_span_id:
            result["parent_span_id"] = self.parent_span_id
        if self.tracestate:
            result["tracestate"] = self.tracestate
        return result

    @classmethod
    def from_otel(cls, span_context: Any) -> "TraceContext":
        """Convert an OpenTelemetry SpanContext to a framework TraceContext."""
        return cls(
            trace_id=format(span_context.trace_id, "032x"),
            span_id=format(span_context.span_id, "016x"),
            tracestate=str(span_context.trace_state) if span_context.trace_state else None,
        )

    def to_otel_span_context(self) -> Any | None:
        """Convert to an OpenTelemetry SpanContext (requires opentelemetry-api)."""
        try:
            from opentelemetry.trace import SpanContext, TraceFlags
            from opentelemetry.trace.span import TraceState

            trace_id = int(self.trace_id, 16)
            span_id = int(self.span_id, 16)
            ts = TraceState.from_header([self.tracestate]) if self.tracestate else TraceState.get_default()
            return SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                is_remote=self.parent_span_id is not None,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
                trace_state=ts,
            )
        except ImportError:
            return None


def parse_trace_context(payload: dict[str, str]) -> TraceContext | None:
    """Parse W3C Trace Context fields from a dict into a TraceContext."""
    trace_id = payload.get("trace_id") or payload.get("traceparent")
    if not trace_id or not isinstance(trace_id, str) or len(trace_id) != 32:
        return None
    span_id = payload.get("span_id", uuid.uuid4().hex[:16])
    parent_span_id = payload.get("parent_span_id")
    tracestate = payload.get("tracestate")
    return TraceContext(
        trace_id=trace_id,
        span_id=span_id if len(span_id) == 16 else uuid.uuid4().hex[:16],
        parent_span_id=parent_span_id if parent_span_id else None,
        tracestate=tracestate,
    )
