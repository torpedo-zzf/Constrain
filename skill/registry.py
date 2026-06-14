from __future__ import annotations

import logging
from typing import Any

from skill.base import BaseSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Central registry for skills.

    Skills are registered by name and version. The registry supports
    discovery, lookup, and lifecycle management.
    """

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}
        self._workflows: dict[str, Any] = {}

    def register(self, skill: BaseSkill) -> None:
        """Register a skill instance.

        Args:
            skill: An instantiated skill.

        Raises:
            ValueError: If a skill with the same name is already registered.
        """
        key = skill.name
        if key in self._skills:
            raise ValueError(f"Skill '{key}' is already registered")
        self._skills[key] = skill

    def get(self, name: str) -> BaseSkill | None:
        """Look up a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, str]]:
        """List all registered skills."""
        return [
            {"name": s.name, "version": s.version, "description": s.description}
            for s in self._skills.values()
        ]

    def register_workflow(self, name: str, workflow_def: Any) -> None:
        """Register a workflow definition by name."""
        self._workflows[name] = workflow_def

    def get_workflow(self, name: str) -> Any | None:
        """Look up a workflow definition by name."""
        return self._workflows.get(name)

    def remove(self, name: str) -> bool:
        """Remove a skill by name."""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def clear(self) -> None:
        """Remove all registered skills."""
        self._skills.clear()
