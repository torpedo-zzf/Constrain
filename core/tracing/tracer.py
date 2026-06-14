from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Generator
from typing import Any

from core.tracing.context import TraceContext, parse_trace_context

logger = logging.getLogger(__name__)


class Span:
    """Framework span — wraps an OpenTelemetry span when available.

    In DEV mode (no OTel SDK), records timing in-process and logs on finish.
    In PRODUCTION mode (OTel configured), delegates to the real OTel span.
    """

    def __init__(
        self,
        name: str,
        trace_context: TraceContext,
        attributes: dict[str, Any] | None = None,
        otel_span: Any = None,
    ) -> None:
        self.name = name
        self.trace_context = trace_context
        self.attributes = attributes or {}
        self._otel_span = otel_span
        self._start_time: float | None = None
        self._end_time: float | None = None

        if otel_span is None:
            self._start_time = time.monotonic()

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value
        if self._otel_span is not None:
            self._otel_span.set_attribute(key, str(value))

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Record an event on this span."""
        if self._otel_span is not None:
            self._otel_span.add_event(name, attributes or {})

    def finish(self, attributes: dict[str, Any] | None = None) -> None:
        """Finish the span."""
        if attributes:
            self.attributes.update(attributes)
        self._end_time = time.monotonic()
        if self._otel_span is not None:
            self._otel_span.end()

    @property
    def duration_ms(self) -> float:
        if self._start_time is None or self._end_time is None:
            return 0.0
        return (self._end_time - self._start_time) * 1000


class Tracer:
    """Tracing facade built on OpenTelemetry.

    Two modes:
      DEV (default) — no external dependencies. Spans are recorded in-memory
      and written to structured logs on finish.

      PRODUCTION — configured with an OTel ``TracerProvider`` and exporter.
      Spans are sent to Jaeger (or any OTLP-compatible backend).

    Usage::

        # DEV mode (zero deps)
        tracer = Tracer()

        # Or configure once at startup for production
        Tracer.configure(
            service_name="my-agent",
            exporter=OTLPSpanExporter(endpoint="http://jaeger:4317"),
            sampling_ratio=0.1,
        )

        # In operation
        ctx = tracer.extract_or_create(event_payload)
        with tracer.start_span(ctx, "process", {"key": "val"}) as span:
            result = do_work()
    """

    def __init__(self, tracer_provider: Any = None) -> None:
        self._provider = tracer_provider
        self._otel_tracer: Any = None

        if tracer_provider is not None:
            try:
                self._otel_tracer = tracer_provider.get_tracer("constrain", "0.1.0")
            except Exception:
                logger.exception("Failed to create OTel tracer")

    # --- Class-level convenience (most users call this) ---

    _instance: Tracer | None = None

    @classmethod
    def configure(
        cls,
        service_name: str = "constrain",
        exporter: Any | None = None,
        sampling_ratio: float = 1.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Configure the global Tracer with an OpenTelemetry pipeline.

        Creates a ``TracerProvider`` with a batch span processor that
        exports to the given exporter. Sets it as the global OTel
        ``TracerProvider`` so that third-party instrumentation also
        picks it up.

        Args:
            service_name: Service name for the ``service.name`` resource attribute.
            exporter: An OTel ``SpanExporter`` instance. If ``None``, uses
                ``OTLPSpanExporter`` reading from ``OTEL_EXPORTER_OTLP_*`` env vars.
            sampling_ratio: Probability [0,1] for head-based sampling.
                1.0 = sample all (default). 0.1 = sample 10%.
            headers: Optional dict of metadata headers for the exporter.

        Raises:
            ImportError: If ``opentelemetry-sdk`` is not installed.
        """
        try:
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME
            from opentelemetry.sdk.trace import TracerProvider as OTelTracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
        except ImportError:
            raise ImportError(
                "opentelemetry-sdk is required for production tracing. "
                "Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp"
            )

        resource = Resource.create({SERVICE_NAME: service_name})
        sampler = ParentBasedTraceIdRatio(sampling_ratio) if sampling_ratio < 1.0 else None

        provider = OTelTracerProvider(resource=resource, sampler=sampler)

        if exporter is None:
            exporter = cls._default_exporter(headers)

        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # Set as global OTel provider so SDK auto-instrumentation hooks in
        try:
            from opentelemetry import trace as otel_trace

            otel_trace.set_tracer_provider(provider)
        except ImportError:
            pass

        cls._instance = cls(provider)
        logger.info(
            "Tracer configured | service=%s sampler_ratio=%.2f exporter=%s",
            service_name,
            sampling_ratio,
            type(exporter).__name__,
        )

    @classmethod
    def _default_exporter(cls, headers: dict[str, str] | None = None) -> Any:
        """Create an OTLP gRPC exporter using environment convention."""
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            return OTLPSpanExporter(headers=headers)
        except ImportError:
            raise ImportError(
                "opentelemetry-exporter-otlp-proto-grpc is required. "
                "Install with: pip install opentelemetry-exporter-otlp"
            )

    @classmethod
    def get_instance(cls) -> Tracer:
        """Return the configured global instance, or a DEV-mode instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # --- Core API ---

    def extract_or_create(self, payload: dict[str, Any]) -> TraceContext:
        """Extract a TraceContext from a dict payload, or create a new root."""
        ctx = parse_trace_context(payload)
        if ctx is not None:
            return ctx
        return TraceContext()

    @contextlib.contextmanager
    def start_span(
        self,
        trace_context: TraceContext,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """Start a new child span.

        In PRODUCTION mode the span is backed by an OTel span and
        exported through the configured pipeline. In DEV mode the span
        is recorded in-process and logged on finish.

        Args:
            trace_context: Parent ``TraceContext``.
            name: Span name (shown in Jaeger).
            attributes: Optional key-value pairs attached to the span.

        Yields:
            A ``Span`` instance; ``.finish()`` is called on exit.
        """
        if self._otel_tracer is not None:
            with self._otel_start_span(trace_context, name, attributes) as span:
                yield span
        else:
            with self._dev_start_span(trace_context, name, attributes) as span:
                yield span

    # --- OTel-backed path ---

    @contextlib.contextmanager
    def _otel_start_span(
        self,
        trace_context: TraceContext,
        name: str,
        attributes: dict[str, Any] | None,
    ) -> Generator[Span, None, None]:
        import opentelemetry.trace as otel_trace

        parent_sc = trace_context.to_otel_span_context()
        token = None
        if parent_sc is not None:
            ctx = otel_trace.set_span_in_context(
                otel_trace.NonRecordingSpan(parent_sc),
            )
            token = otel_trace.attach(ctx)

        with self._otel_tracer.start_as_current_span(name) as otel_span:
            child_ctx = TraceContext.from_otel(otel_span.get_span_context())
            span = Span(name, child_ctx, attributes, otel_span=otel_span)
            if attributes:
                for k, v in attributes.items():
                    otel_span.set_attribute(k, _to_otel_value(v))
            try:
                yield span
            finally:
                if token:
                    otel_trace.detach(token)

    # --- DEV (in-memory) path ---

    @contextlib.contextmanager
    def _dev_start_span(
        self,
        trace_context: TraceContext,
        name: str,
        attributes: dict[str, Any] | None,
    ) -> Generator[Span, None, None]:
        child_ctx = trace_context.new_child()
        span = Span(name, child_ctx, attributes)
        try:
            yield span
        finally:
            span.finish()
            logger.debug(
                "Span | %s | duration=%.1fms | trace=%s span=%s parent=%s | %s",
                span.name,
                span.duration_ms,
                span.trace_context.trace_id,
                span.trace_context.span_id,
                span.trace_context.parent_span_id or "-",
                span.attributes,
            )


# --- Class-level convenience proxies (backwards-compatible API) ---

def _to_otel_value(v: Any) -> str | bool | float | int:
    """Coerce a Python value to an OTel-allowed attribute type."""
    if isinstance(v, (bool, int, float, str)):
        return v  # type: ignore[return-value]
    return str(v)


def configure_tracer(
    service_name: str = "constrain",
    exporter: Any | None = None,
    sampling_ratio: float = 1.0,
) -> None:
    """Convenience function to configure the global tracer at startup."""
    Tracer.configure(
        service_name=service_name,
        exporter=exporter,
        sampling_ratio=sampling_ratio,
    )
