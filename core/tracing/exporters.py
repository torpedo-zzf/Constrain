from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LoggingSpanExporter:
    """DEV-mode span exporter that logs spans as structured JSON.

    Drops the data after logging — no external collector needed.
    Implements the OpenTelemetry SpanExporter duck-type interface.
    """

    def __init__(self, logger_name: str = "constrain.tracing") -> None:
        self._log = logging.getLogger(logger_name)

    def export(self, spans: list[Any]) -> int:
        """Export a batch of spans.

        Args:
            spans: List of opentelemetry ReadableSpan objects.

        Returns:
            Status code (0 = SUCCESS, 1 = FAILURE).
        """
        for span in spans:
            attrs = dict(span.attributes) if span.attributes else {}
            self._log.info(
                "Span | %s | duration=%.1fms | trace=%s span=%s parent=%s | %s",
                span.name,
                (span.end_time - span.start_time) / 1e6 if span.end_time and span.start_time else 0,
                format(span.context.trace_id, "032x") if span.context else "?",
                format(span.context.span_id, "016x") if span.context else "?",
                format(span.parent.span_id, "016x") if span.parent else "-",
                attrs,
            )
        return 0

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def create_jaeger_exporter(
    endpoint: str = "http://localhost:4317",
    insecure: bool = True,
    timeout: int = 10,
    headers: dict[str, str] | None = None,
) -> Any:
    """Create an OTLP SpanExporter configured for Jaeger.

    Jaeger natively accepts OTLP since Jaeger v1.35.
    Uses gRPC by default; set ``OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf``
    at the process level to switch to HTTP.

    Args:
        endpoint: Jaeger OTLP endpoint URL (default: ``http://localhost:4317``).
        insecure: Use insecure gRPC connection (default: True).
        timeout: Export timeout in seconds.
        headers: Optional gRPC metadata headers (e.g., auth tokens).

    Returns:
        An ``OTLPSpanExporter`` instance, or raises ``ImportError``
        if ``opentelemetry-exporter-otlp-proto-grpc`` is not installed.

    Raises:
        ImportError: If the OTLP exporter package is missing.
    """
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
    except ImportError:
        raise ImportError(
            "opentelemetry-exporter-otlp-proto-grpc is required for Jaeger export. "
            "Install with: pip install opentelemetry-exporter-otlp"
        )

    return OTLPSpanExporter(
        endpoint=endpoint,
        insecure=insecure,
        timeout=timeout,
        headers=headers,
    )


def is_otel_available() -> bool:
    """Check whether the OpenTelemetry SDK is importable."""
    try:
        import opentelemetry  # noqa: F401
        return True
    except ImportError:
        return False
