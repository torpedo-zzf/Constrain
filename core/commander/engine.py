from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from core.commander.models import (
    Edge,
    EdgeCondition,
    TaskDef,
    TaskStatus,
    WorkflowDef,
    WorkflowStatus,
)
from core.commander.scheduler import DAGScheduler
from core.event_bus import Event, EventBus

logger = logging.getLogger(__name__)


class CommanderEngine:
    """Workflow orchestration engine.

    Receives workflow definitions, parses the DAG, dispatches tasks to the
    EventBus, and tracks execution progress. Does not execute any business logic.
    Stateless — recovering instances re-subscribe to event streams.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._workflows: dict[str, WorkflowStatus] = {}
        self._definitions: dict[str, WorkflowDef] = {}
        self._schedulers: dict[str, DAGScheduler] = {}

        # Subscribe to lifecycle events
        # (external code must ensure these subscriptions are active after start)
        self._registered = False

    async def register_handlers(self) -> None:
        """Subscribe to task lifecycle events from the event bus."""
        if self._registered:
            return
        await self._event_bus.subscribe("TaskCompleted", self._on_task_completed, "commander")
        await self._event_bus.subscribe("TaskFailed", self._on_task_failed, "commander")
        await self._event_bus.subscribe("TaskStarted", self._on_task_started, "commander")
        self._registered = True

    async def submit_workflow(self, workflow_def: WorkflowDef, input_data: dict[str, Any]) -> str:
        """Submit a workflow definition for execution.

        Args:
            workflow_def: The workflow DAG definition.
            input_data: Global input data available to all tasks via input_mapping.

        Returns:
            The unique run_id for tracking.
        """
        run_id = uuid4().hex
        self._definitions[run_id] = workflow_def
        self._schedulers[run_id] = DAGScheduler(workflow_def.tasks, workflow_def.edges)

        status = WorkflowStatus(
            run_id=run_id,
            workflow_name=workflow_def.name,
            status="PENDING",
            task_statuses={t.task_id: TaskStatus.PENDING for t in workflow_def.tasks},
            context={"input": input_data},
        )
        self._workflows[run_id] = status

        # Broadcast workflow submission event
        event = Event.create(
            event_type="WorkflowSubmitted",
            payload={"run_id": run_id, "workflow_name": workflow_def.name, "input": input_data},
        )
        await self._event_bus.publish(event, routing_key="workflow.submitted")

        # Dispatch initial ready tasks
        ready = self._schedulers[run_id].get_ready_tasks(set(), set())
        for task_def in ready:
            await self._dispatch_task(run_id, task_def, input_data)

        status.status = "RUNNING"
        return run_id

    async def get_status(self, run_id: str) -> WorkflowStatus | None:
        """Get the current execution status of a workflow."""
        return self._workflows.get(run_id)

    async def cancel_workflow(self, run_id: str) -> bool:
        """Cancel a running workflow."""
        status = self._workflows.get(run_id)
        if status is None or status.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return False

        status.status = "CANCELLED"
        event = Event.create(
            event_type="WorkflowCancelled",
            payload={"run_id": run_id},
        )
        await self._event_bus.publish(event, routing_key="workflow.cancelled")
        return True

    async def insert_task(
        self, run_id: str, task: TaskDef, after_task_id: str
    ) -> bool:
        """Dynamically insert a new task into a running workflow.

        Args:
            run_id: The target workflow run.
            task: The task definition to insert.
            after_task_id: Existing task to insert after.

        Returns:
            True if the task was inserted.
        """
        wf = self._definitions.get(run_id)
        if wf is None:
            return False

        wf.tasks.append(task)
        wf.edges.append(Edge(source=after_task_id, target=task.task_id))
        self._schedulers[run_id] = DAGScheduler(wf.tasks, wf.edges)

        status = self._workflows.get(run_id)
        if status:
            status.task_statuses[task.task_id] = TaskStatus.PENDING

        logger.info("Task %s inserted after %s in workflow %s", task.task_id, after_task_id, run_id)
        return True

    async def _dispatch_task(self, run_id: str, task_def: TaskDef, global_input: dict[str, Any]) -> None:
        """Publish a task event to the event bus for execution."""
        status = self._workflows.get(run_id)
        if status is None:
            return

        # Resolve input via input_mapping
        task_input: dict[str, Any] = {}
        for key, value in task_def.input_mapping.items():
            if isinstance(value, str) and value.startswith("$input."):
                input_key = value[7:]
                task_input[key] = global_input.get(input_key)
            else:
                task_input[key] = value

        status.task_statuses[task_def.task_id] = TaskStatus.RUNNING

        event = Event.create(
            event_type="TaskDispatched",
            payload={
                "run_id": run_id,
                "task_id": task_def.task_id,
                "skill_name": task_def.skill_name,
                "input": task_input,
                "timeout": task_def.timeout,
                "retry_policy": task_def.retry_policy,
            },
        )
        await self._event_bus.publish(event, routing_key=f"task.{task_def.skill_name}")

    async def _on_task_started(self, event: Event) -> None:
        run_id = event.payload.get("run_id", "")
        task_id = event.payload.get("task_id", "")
        status = self._workflows.get(run_id)
        if status:
            status.task_statuses[task_id] = TaskStatus.RUNNING

    async def _on_task_completed(self, event: Event) -> None:
        run_id = event.payload.get("run_id", "")
        task_id = event.payload.get("task_id", "")
        status = self._workflows.get(run_id)
        if status is None:
            return

        status.task_statuses[task_id] = TaskStatus.SUCCEEDED
        completed = {tid for tid, ts in status.task_statuses.items() if ts == TaskStatus.SUCCEEDED}
        failed = {tid for tid, ts in status.task_statuses.items() if ts == TaskStatus.FAILED}
        scheduler = self._schedulers.get(run_id)

        if scheduler and scheduler.is_complete(completed, failed):
            status.status = "SUCCEEDED" if not failed else "FAILED"
            status.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            await self._event_bus.publish(
                Event.create("WorkflowCompleted", {"run_id": run_id, "status": status.status}),
                "workflow.completed",
            )
        elif scheduler:
            ready = scheduler.get_ready_tasks(completed, failed)
            for task_def in ready:
                await self._dispatch_task(run_id, task_def, status.context.get("input", {}))

    async def _on_task_failed(self, event: Event) -> None:
        run_id = event.payload.get("run_id", "")
        task_id = event.payload.get("task_id", "")
        status = self._workflows.get(run_id)
        if status is None:
            return

        status.task_statuses[task_id] = TaskStatus.FAILED
        scheduler = self._schedulers.get(run_id)

        completed = {tid for tid, ts in status.task_statuses.items() if ts == TaskStatus.SUCCEEDED}
        failed = {tid for tid, ts in status.task_statuses.items() if ts in (TaskStatus.FAILED, TaskStatus.TIMEOUT)}

        if scheduler and scheduler.is_complete(completed, failed):
            status.status = "FAILED"
            status.error = event.payload.get("error", "Unknown error")
            status.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            await self._event_bus.publish(
                Event.create("WorkflowCompleted", {"run_id": run_id, "status": "FAILED", "error": status.error}),
                "workflow.completed",
            )
