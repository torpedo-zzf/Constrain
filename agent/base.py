from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from core.event_bus import Event, EventBus

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for Agents.

    Agents are long-running workers that subscribe to the EventBus,
    process task events, execute the appropriate Skill, and publish
    results. They are stateless — all context is carried in event payloads.
    """

    name: str = ""
    description: str = ""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._handlers: dict[str, Callable] = {}

    async def start(self) -> None:
        """Subscribe the agent to its task event type."""
        await self._event_bus.subscribe(
            f"task.{self.name}",
            self._handle_event,
            f"agent:{self.name}",
        )
        logger.info("Agent started | name=%s", self.name)

    async def _handle_event(self, event: Event) -> None:
        """Handle an incoming task event from the event bus."""
        payload = event.payload
        task_id = payload.get("task_id", "")
        run_id = payload.get("run_id", "")
        skill_name = payload.get("skill_name", "")
        task_input = payload.get("input", {})
        trace_id = event.trace_id or ""

        logger.info("Agent processing | task=%s skill=%s run=%s", task_id, skill_name, run_id)

        # Emit TaskStarted
        await self._event_bus.publish(
            Event.create(
                "TaskStarted",
                {"run_id": run_id, "task_id": task_id, "skill_name": skill_name},
                trace_id=trace_id,
                source=f"agent:{self.name}",
            ),
            routing_key="task.started",
        )

        try:
            result = await self.execute(skill_name, task_input, trace_id)

            await self._event_bus.publish(
                Event.create(
                    "TaskCompleted",
                    {"run_id": run_id, "task_id": task_id, "result": result},
                    trace_id=trace_id,
                    source=f"agent:{self.name}",
                ),
                routing_key="task.completed",
            )
        except Exception as e:
            logger.exception("Task failed | task=%s run=%s", task_id, run_id)
            await self._event_bus.publish(
                Event.create(
                    "TaskFailed",
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    trace_id=trace_id,
                    source=f"agent:{self.name}",
                ),
                routing_key="task.failed",
            )

    @abstractmethod
    async def execute(self, skill_name: str, input_data: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Execute a named skill with the given input.

        Args:
            skill_name: Name of the skill to execute.
            input_data: Resolved task input from the workflow.
            trace_id: Correlation trace ID.

        Returns:
            Execution result as a serializable dict.
        """
