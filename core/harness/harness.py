from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from core.arbiter import Arbiter
from core.commander import CommanderEngine
from core.event_bus import EventBus
from core.event_bus.backends import MemoryEventBus, RabbitMQEventBus, RedisPubSubEventBus
from core.gate import GatePipeline
from core.harness.config import BusBackend, HarnessConfig
from core.harness.middleware import (
    GateMiddleware,
    LoggingMiddleware,
    Middleware,
    MiddlewareChain,
    TracingMiddleware,
)
from core.state_machine import StateMachine
from core.tracing import configure_tracer, LoggingSpanExporter
from skill import BaseSkill, SkillRegistry

logger = logging.getLogger(__name__)


class Harness:
    """Top-level coordinator that assembles all core components.

    Provides the unified entry point for workflow execution and lifecycle management.
    Supports progressive complexity: zero-dependency memory mode out of the box,
    switch to production backends via configuration.
    """

    def __init__(self, config: HarnessConfig | None = None) -> None:
        self._config = config or HarnessConfig()
        self._config.apply_env_overrides()

        # Components (assembled in start())
        self._event_bus: EventBus | None = None
        self._commander: CommanderEngine | None = None
        self._arbiter: Arbiter | None = None
        self._state_machine: StateMachine | None = None
        self._gate: GatePipeline | None = None

        # Plugin system
        self._skill_registry = SkillRegistry()
        self._middleware_chain = MiddlewareChain()
        self._lifecycle_hooks: dict[str, Any] = {}

        # Runtime state
        self._running = False
        self._background_tasks: set[asyncio.Task[Any]] = set()

    # --- Public API ---

    async def execute_workflow(self, name: str, input_data: dict[str, Any]) -> str:
        """Execute a workflow by name with the given input.

        Args:
            name: The workflow definition name.
            input_data: Input data for the workflow.

        Returns:
            The run_id for tracking execution progress.
        """
        from core.commander.models import WorkflowDef

        # Look up workflow definition from registry or disk
        wf = self._load_workflow(name)
        if wf is None:
            raise ValueError(f"Workflow '{name}' not found. Register it first or place it in workflows/.")

        run_id = await self._commander.submit_workflow(wf, input_data)
        logger.info("Workflow submitted | name=%s run_id=%s", name, run_id)
        return run_id

    async def get_status(self, run_id: str) -> Any | None:
        """Get the current execution status of a workflow run.

        Args:
            run_id: The run ID returned by ``execute_workflow``.

        Returns:
            A ``WorkflowStatus`` or ``None`` if not found.
        """
        if self._commander is None:
            return None
        return await self._commander.get_status(run_id)

    async def start(self) -> None:
        """Initialize all components and start the event bus."""
        if self._running:
            return

        # 1. Create event bus
        self._event_bus = self._create_event_bus()

        # 2. Core engines
        self._arbiter = Arbiter()
        self._state_machine = StateMachine()
        self._commander = CommanderEngine(self._event_bus)
        self._gate = GatePipeline(
            l2_confidence_threshold=self._config.l2_confidence_threshold
        )

        # 3. Wire up state machine to emit events
        self._state_machine.on_state_change(self._on_state_change)

        # 4. Initialize tracing
        if self._config.tracing_enabled:
            self._init_tracing()

        # 5. Set up default middleware
        if self._config.tracing_enabled:
            self._middleware_chain.use(TracingMiddleware())
        self._middleware_chain.use(LoggingMiddleware())
        self._middleware_chain.use(GateMiddleware(self._gate))

        # 5. Start event bus and register handlers
        await self._event_bus.start()
        await self._commander.register_handlers()

        # 6. Auto-discover skills
        self._discover_skills()

        self._running = True
        logger.info("Harness started | mode=%s", self._config.mode)

    async def shutdown(self) -> None:
        """Gracefully shut down all components."""
        if not self._running:
            return
        self._running = False

        logger.info("Shutting down harness...")

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        await self._event_bus.stop()
        logger.info("Harness shutdown complete")

    def register_skill(self, skill: BaseSkill) -> None:
        """Register a skill with the framework."""
        self._skill_registry.register(skill)
        logger.info("Skill registered | name=%s version=%s", skill.name, skill.version)

    def use_middleware(self, middleware: Middleware) -> None:
        """Register a middleware in the chain."""
        self._middleware_chain.use(middleware)

    def on(self, event: str, handler: Any) -> None:
        """Register a lifecycle hook."""
        self._lifecycle_hooks[event] = handler

    # --- Internal ---

    def _create_event_bus(self) -> EventBus:
        backend = self._config.bus_backend
        if backend == BusBackend.MEMORY:
            return MemoryEventBus()
        elif backend == BusBackend.RABBITMQ:
            return RabbitMQEventBus(url=self._config.rabbitmq_url)
        elif backend == BusBackend.REDIS_PUBSUB:
            return RedisPubSubEventBus(url=self._config.redis_url)
        raise ValueError(f"Unknown bus backend: {backend}")

    def _init_tracing(self) -> None:
        """Initialize the tracing pipeline based on configuration."""
        cfg = self._config

        if cfg.tracing_mode.value == "production":
            from core.tracing import create_jaeger_exporter

            try:
                exporter = create_jaeger_exporter(
                    endpoint=cfg.jaeger_endpoint,
                    insecure=cfg.jaeger_insecure,
                )
                configure_tracer(
                    service_name=cfg.tracing_service_name,
                    exporter=exporter,
                    sampling_ratio=cfg.sampling_rate,
                )
                logger.info(
                    "Tracing initialized | mode=production service=%s endpoint=%s ratio=%.2f",
                    cfg.tracing_service_name,
                    cfg.jaeger_endpoint,
                    cfg.sampling_rate,
                )
            except ImportError as e:
                logger.warning(
                    "Failed to configure OTel tracing (%s). Falling back to DEV mode.",
                    e,
                )
                configure_tracer(
                    service_name=cfg.tracing_service_name,
                    sampling_ratio=cfg.sampling_rate,
                )
        else:
            # DEV mode — logging exporter
            exporter = LoggingSpanExporter()
            try:
                configure_tracer(
                    service_name=cfg.tracing_service_name,
                    exporter=exporter,
                    sampling_ratio=cfg.sampling_rate,
                )
            except ImportError:
                # OTel SDK not available — use pure DEV mode (no exporter needed)
                pass
            logger.info(
                "Tracing initialized | mode=dev service=%s",
                cfg.tracing_service_name,
            )

    def _load_workflow(self, name: str) -> Any:
        from pathlib import Path

        from core.commander.models import WorkflowDef

        # Check file system
        for ext in ("yaml", "yml", "json"):
            path = Path(f"workflows/{name}.{ext}")
            if path.exists():
                import yaml

                with open(path) as f:
                    data = yaml.safe_load(f) if ext != "json" else __import__("json").load(f)
                if data.get("name") != name:
                    data["name"] = name
                return WorkflowDef(**data)

        # Check in-memory registry
        return self._skill_registry.get_workflow(name)

    def _discover_skills(self) -> None:
        """Auto-discover and register skills from configured paths."""
        for path_str in self._config.skill_paths:
            from pathlib import Path

            p = Path(path_str)
            if not p.is_dir():
                continue
            self._import_skills_from(p)

    def _import_skills_from(self, path: Path) -> None:
        """Recursively import Python modules and register Skill subclasses."""
        import importlib
        import inspect

        for py_file in path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    py_file.stem, py_file
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BaseSkill)
                        and obj is not BaseSkill
                        and hasattr(obj, "name")
                    ):
                        instance = obj()
                        self.register_skill(instance)
            except Exception:
                logger.exception("Failed to load skill from %s", py_file)

    def _on_state_change(self, event: Any) -> None:
        """Handle state machine state changes by emitting events."""
        # This could publish state change events to the bus
        logger.debug("State change | %s: %s -> %s", event.entity_id, event.from_state, event.to_state)

    async def _run_with_graceful_shutdown(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()
        stop = loop.create_future()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(
                    sig, lambda: stop.set_result(None)
                )
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        await stop
        await self.shutdown()
