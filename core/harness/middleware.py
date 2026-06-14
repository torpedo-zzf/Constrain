from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from core.tracing import Tracer

logger = logging.getLogger(__name__)

NextHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class Middleware(ABC):
    """Pluggable middleware interface following the onion model."""

    @abstractmethod
    async def handle(self, context: dict[str, Any], next_handler: NextHandler) -> dict[str, Any]:
        """Process a context and optionally call the next handler.

        Args:
            context: Execution context dict (e.g., task input, trace info).
            next_handler: The next middleware or the actual handler.

        Returns:
            The processed result dict.
        """


class MiddlewareChain:
    """Chain of middleware executed in onion/onion model order.

    Middleware added first wraps closest to the core handler.
    """

    def __init__(self) -> None:
        self._middleware: list[Middleware] = []

    def use(self, middleware: Middleware) -> None:
        """Register a middleware at the end of the chain."""
        self._middleware.append(middleware)

    def build(self, handler: NextHandler) -> NextHandler:
        """Wrap the handler with all middleware layers."""
        current = handler
        for mw in reversed(self._middleware):
            mw_instance = mw

            async def wrapper(ctx: dict[str, Any], mw=mw_instance, next_h=current) -> dict[str, Any]:
                return await mw.handle(ctx, next_h)

            current = wrapper
        return current


class LoggingMiddleware(Middleware):
    """Middleware that logs execution context before and after processing."""

    async def handle(self, context: dict[str, Any], next_handler: NextHandler) -> dict[str, Any]:
        logger.debug("Middleware | before | context_keys=%s", list(context.keys()))
        result = await next_handler(context)
        logger.debug("Middleware | after | result_keys=%s", list(result.keys()))
        return result


class TracingMiddleware(Middleware):
    """Middleware that injects and propagates trace context.

    Uses the global ``Tracer`` instance. Works in both DEV and PRODUCTION
    tracing modes.
    """

    async def handle(self, context: dict[str, Any], next_handler: NextHandler) -> dict[str, Any]:
        tracer = Tracer.get_instance()
        trace_ctx = tracer.extract_or_create(context)
        context["trace_id"] = trace_ctx.trace_id

        with tracer.start_span(trace_ctx, "middleware", {"component": "harness"}):
            return await next_handler(context)


class GateMiddleware(Middleware):
    """Middleware that runs a gate pipeline on task output."""

    def __init__(self, gate_pipeline: Any) -> None:
        self._gate = gate_pipeline

    async def handle(self, context: dict[str, Any], next_handler: NextHandler) -> dict[str, Any]:
        result = await next_handler(context)
        if self._gate:
            gate_result = await self._gate.evaluate(result)
            if gate_result.verdict.value == "reject":
                raise RuntimeError(f"Gate rejected output: {gate_result.layer_name} | {gate_result.rule_results}")
        return result
