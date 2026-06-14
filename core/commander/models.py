from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EdgeCondition(BaseModel):
    """Condition attached to a DAG edge for conditional branching."""
    type: str = "always"  # always, success, failure, expression
    expression: str | None = None


class Edge(BaseModel):
    """Directed edge between two tasks in a workflow DAG."""
    source: str
    target: str
    condition: EdgeCondition = Field(default_factory=EdgeCondition)


class TaskDef(BaseModel):
    """Definition of a single task node in a workflow."""
    task_id: str
    skill_name: str
    input_mapping: dict[str, Any] = Field(default_factory=dict)
    timeout: int = 300
    retry_policy: str = "default"
    depends_on: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowDef(BaseModel):
    """Complete workflow definition as a DAG of tasks."""
    name: str
    version: str
    tasks: list[TaskDef]
    edges: list[Edge]
    metadata: dict[str, Any] = Field(default_factory=dict)
    timeout: int = 3600


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    TIMEOUT = "TIMEOUT"


class WorkflowStatus(BaseModel):
    """Runtime status of a workflow execution."""
    run_id: str
    workflow_name: str
    status: str = "PENDING"
    task_statuses: dict[str, TaskStatus] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
