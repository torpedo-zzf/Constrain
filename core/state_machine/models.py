from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TransitionError(Exception):
    """Raised when an illegal state transition is attempted."""


class State(BaseModel):
    """Current state of an entity in the state machine."""

    entity_type: str
    entity_id: str
    current_state: str
    context: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_seconds: int | None = None

    model_config = {"frozen": False}


class StateChangeEvent(BaseModel):
    """Record of a single state transition, persisted for event sourcing."""

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    entity_type: str
    entity_id: str
    from_state: str
    to_state: str
    event_data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str | None = None


class Transition(BaseModel):
    """Defines a permitted state transition between two states."""
    from_state: str
    to_state: str


class StateDefinition(BaseModel):
    """Defines a state and its allowed outgoing transitions."""

    state: str
    allowed_transitions: list[str] = Field(default_factory=list)
    timeout_seconds: int | None = None


class StateStore(ABC):
    """Abstract storage backend for state machine data."""

    @abstractmethod
    async def save_state(self, state: State) -> None:
        ...

    @abstractmethod
    async def get_state(self, entity_id: str) -> State | None:
        ...

    @abstractmethod
    async def append_event(self, event: StateChangeEvent) -> None:
        ...

    @abstractmethod
    async def get_events(self, entity_id: str) -> list[StateChangeEvent]:
        ...


class InMemoryStateStore(StateStore):
    """In-memory implementation for development/testing."""

    def __init__(self) -> None:
        self._states: dict[str, State] = {}
        self._events: dict[str, list[StateChangeEvent]] = {}

    async def save_state(self, state: State) -> None:
        state.updated_at = datetime.now(timezone.utc)
        self._states[state.entity_id] = state

    async def get_state(self, entity_id: str) -> State | None:
        return self._states.get(entity_id)

    async def append_event(self, event: StateChangeEvent) -> None:
        self._events.setdefault(event.entity_id, []).append(event)

    async def get_events(self, entity_id: str) -> list[StateChangeEvent]:
        return self._events.get(entity_id, [])
