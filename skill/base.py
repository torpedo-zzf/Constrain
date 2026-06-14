from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseSkill(ABC):
    """Abstract base class for all Skills.

    A Skill is a single unit of work that can be executed by the framework.
    Skills are registered with the Harness and dispatched by the Commander.
    """

    name: str = ""
    version: str = "0.1.0"
    description: str = ""

    def validate_input(self, input_data: dict[str, Any]) -> bool:
        """Validate input data before execution.

        Override this method to provide input validation.
        Returns True if input is valid, raises otherwise.

        Args:
            input_data: Raw input dict from the task dispatch.

        Returns:
            True if valid.
        """
        return True

    @abstractmethod
    async def execute(
        self,
        input_data: dict[str, Any],
        parameters: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        """Execute the skill's business logic.

        Args:
            input_data: Resolved task input data.
            parameters: Configuration parameters for this execution.
            trace_id: Trace ID for observability correlation.

        Returns:
            Execution result as a serializable dict.
        """
