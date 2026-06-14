from __future__ import annotations

from typing import Any

from agent.base import BaseAgent


class AgentRegistry:
    """Registry for Agent instances."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        key = agent.name
        if key in self._agents:
            raise ValueError(f"Agent '{key}' is already registered")
        self._agents[key] = agent

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[dict[str, str]]:
        return [
            {"name": a.name, "description": a.description}
            for a in self._agents.values()
        ]

    async def start_all(self) -> None:
        for agent in self._agents.values():
            await agent.start()
