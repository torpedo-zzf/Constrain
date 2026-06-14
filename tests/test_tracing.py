from core.tracing import TraceContext, Tracer


class TestTraceContext:
    def test_create_new(self):
        ctx = TraceContext()
        assert len(ctx.trace_id) == 32
        assert len(ctx.span_id) == 16
        assert ctx.parent_span_id is None

    def test_child_context(self):
        parent = TraceContext()
        child = parent.new_child()
        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id
        assert child.span_id != parent.span_id

    def test_to_otel_dict(self):
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            parent_span_id="c" * 16,
        )
        d = ctx.to_otel_dict()
        assert d["trace_id"] == "a" * 32
        assert d["span_id"] == "b" * 16
        assert d["parent_span_id"] == "c" * 16

    def test_tracestate_roundtrip(self):
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            tracestate="rojo=00f067aa0ba902b7",
        )
        d = ctx.to_otel_dict()
        assert d["tracestate"] == "rojo=00f067aa0ba902b7"


class TestTracerDevMode:
    """Tests against the DEV-mode Tracer (no OTel SDK needed)."""

    def test_extract_or_create_from_payload(self):
        tracer = Tracer()
        ctx = tracer.extract_or_create({
            "trace_id": "a" * 32,
            "span_id": "b" * 16,
        })
        assert ctx.trace_id == "a" * 32
        assert ctx.span_id == "b" * 16

    def test_extract_or_create_new(self):
        tracer = Tracer()
        ctx = tracer.extract_or_create({"some": "data"})
        assert len(ctx.trace_id) == 32

    def test_start_span(self):
        tracer = Tracer()
        parent = TraceContext()
        with tracer.start_span(parent, "test_span", {"key": "val"}) as span:
            assert span.name == "test_span"
            assert span.attributes.get("key") == "val"
            assert span.trace_context.parent_span_id == parent.span_id
            assert span.duration_ms == 0.0  # not yet finished

    def test_span_finish(self):
        tracer = Tracer()
        with tracer.start_span(TraceContext(), "s") as span:
            span.set_attribute("k", "v")
            span.add_event("hit", {"count": 1})
        assert span.duration_ms > 0
        assert span.attributes["k"] == "v"

    def test_get_instance_defaults_to_dev(self):
        tracer = Tracer.get_instance()
        assert isinstance(tracer, Tracer)
        # start_span should work without OTel
        with tracer.start_span(TraceContext(), "dev_check") as span:
            assert span.name == "dev_check"

    def test_parse_w3c_traceparent(self):
        from core.tracing import parse_trace_context

        ctx = parse_trace_context({"traceparent": "a" * 32, "span_id": "b" * 16})
        assert ctx is not None
        assert ctx.trace_id == "a" * 32
        assert ctx.span_id == "b" * 16

    def test_logging_exporter(self):
        from core.tracing import LoggingSpanExporter

        exporter = LoggingSpanExporter()
        assert exporter.export([]) == 0
        assert exporter.force_flush() is True
        exporter.shutdown()  # no-op, should not raise
