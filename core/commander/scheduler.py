from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Any

from core.commander.models import Edge, EdgeCondition, TaskDef, TaskStatus


class ScheduleStrategy(str, Enum):
    SERIAL = "serial"
    PARALLEL = "parallel"
    FAN_OUT_FAN_IN = "fan_out_fan_in"
    CONDITIONAL = "conditional"


class DAGScheduler:
    """DAG-based workflow task scheduler.

    Resolves dependency order and determines which tasks are ready to execute.
    """

    def __init__(self, tasks: list[TaskDef], edges: list[Edge]) -> None:
        self._tasks = {t.task_id: t for t in tasks}
        self._edges = edges

        # adjacency list + reverse graph
        self._graph: dict[str, list[str]] = {t.task_id: [] for t in tasks}
        self._in_degree: dict[str, int] = {t.task_id: 0 for t in tasks}
        for edge in edges:
            self._graph.setdefault(edge.source, []).append(edge.target)
            self._in_degree[edge.target] = self._in_degree.get(edge.target, 0) + 1

    def get_ready_tasks(self, completed: set[str], failed: set[str]) -> list[TaskDef]:
        """Return tasks whose dependencies are satisfied."""
        ready: list[TaskDef] = []
        for task_id, task in self._tasks.items():
            if task_id in completed or task_id in failed:
                continue

            deps = [e.source for e in self._edges if e.target == task_id]

            # Evaluate edge conditions
            all_deps_ready = True
            for dep in deps:
                edge = next((e for e in self._edges if e.source == dep and e.target == task_id), None)
                if edge is None:
                    continue

                if edge.condition.type == "always":
                    if dep not in completed:
                        all_deps_ready = False
                elif edge.condition.type == "success":
                    if dep not in completed:
                        all_deps_ready = False
                elif edge.condition.type == "failure":
                    if dep not in failed:
                        all_deps_ready = False
                elif edge.condition.type == "expression":
                    if dep not in completed:
                        all_deps_ready = False

            if all_deps_ready and deps:
                ready.append(task)
            elif not deps and task_id not in completed:
                ready.append(task)

        return ready

    def is_complete(self, completed: set[str], failed: set[str]) -> bool:
        """Check whether every task has either completed or failed."""
        return len(completed) + len(failed) == len(self._tasks)

    def get_execution_order(self) -> list[list[str]]:
        """Topological sort returning layers of parallel-executable tasks."""
        in_degree = dict(self._in_degree)
        queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
        layers: list[list[str]] = []

        while queue:
            layer: list[str] = []
            for _ in range(len(queue)):
                tid = queue.popleft()
                layer.append(tid)
                for neighbor in self._graph.get(tid, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            layers.append(layer)

        return layers

    def get_downstream(self, task_id: str) -> list[str]:
        """Get all tasks that depend (directly or transitively) on the given task."""
        visited: set[str] = set()
        stack = [task_id]
        while stack:
            tid = stack.pop()
            for neighbor in self._graph.get(tid, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        return list(visited)
