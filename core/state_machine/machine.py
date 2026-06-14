from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from core.state_machine.models import (
    InMemoryStateStore,
    State,
    StateChangeEvent,
    StateDefinition,
    StateStore,
    TransitionError,
)

logger = logging.getLogger(__name__)

StateChangeHandler = Callable[[StateChangeEvent], None]


class StateMachine:
    """State machine enforcing strict transition rules with event sourcing.

    Predefined lifecycle:
        PENDING -> RUNNING -> SUCCEEDED
                            -> FAILED
                            -> PAUSED -> RUNNING
                                      -> CANCELLED
                            -> TIMEOUT
                            -> WAITING_USER_INPUT -> RUNNING

    Supports custom state definitions with permitted transitions,
    pause/resume semantics, and event-driven state recovery.
    """

    _PREDEFINED: dict[str, StateDefinition] = {
        "PENDING": StateDefinition(state="PENDING", allowed_transitions=["RUNNING", "CANCELLED"]),
        "RUNNING": StateDefinition(
            state="RUNNING",
            allowed_transitions=["SUCCEEDED", "FAILED", "PAUSED", "TIMEOUT", "WAITING_USER_INPUT"],
        ),
        "SUCCEEDED": StateDefinition(state="SUCCEEDED", allowed_transitions=[]),
        "FAILED": StateDefinition(state="FAILED", allowed_transitions=[]),
        "PAUSED": StateDefinition(state="PAUSED", allowed_transitions=["RUNNING", "CANCELLED"]),
        "CANCELLED": StateDefinition(state="CANCELLED", allowed_transitions=[]),
        "TIMEOUT": StateDefinition(state="TIMEOUT", allowed_transitions=["RUNNING"]),
        "WAITING_USER_INPUT": StateDefinition(
            state="WAITING_USER_INPUT", allowed_transitions=["RUNNING", "CANCELLED"]
        ),
    }

    def __init__(
        self,
        store: StateStore | None = None,
        custom_states: list[StateDefinition] | None = None,
    ) -> None:
        self._store = store or InMemoryStateStore()
        self._on_change: list[StateChangeHandler] = []

        self._definitions: dict[str, StateDefinition] = dict(self._PREDEFINED)
        if custom_states:
            for sd in custom_states:
                self._definitions[sd.state] = sd

    def on_state_change(self, handler: StateChangeHandler) -> None:
        """Register a callback invoked on every successful transition."""
        self._on_change.append(handler)

    async def create_instance(
        self,
        entity_type: str,
        entity_id: str,
        initial_state: str = "PENDING",
        context: dict[str, Any] | None = None,
    ) -> None:
        """Create a new state machine instance."""
        if initial_state not in self._definitions:
            raise ValueError(f"Unknown initial state: {initial_state}")

        existing = await self._store.get_state(entity_id)
        if existing is not None:
            raise ValueError(f"Entity {entity_id} already exists in state {existing.current_state}")

        state = State(
            entity_type=entity_type,
            entity_id=entity_id,
            current_state=initial_state,
            context=context or {},
        )
        await self._store.save_state(state)

        event = StateChangeEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state="",
            to_state=initial_state,
            event_data={"initial_context": context or {}},
        )
        await self._store.append_event(event)
        self._notify(event)

    async def transition(
        self, entity_id: str, to_state: str, event_data: dict[str, Any] | None = None
    ) -> StateChangeEvent:
        """Transition an entity to a new state, validating legality."""
        state = await self._store.get_state(entity_id)
        if state is None:
            raise ValueError(f"Entity {entity_id} not found. Call create_instance first.")

        definition = self._definitions.get(state.current_state)
        if definition is None:
            raise TransitionError(f"No definition for current state {state.current_state}")

        if to_state not in definition.allowed_transitions:
            raise TransitionError(
                f"Illegal transition: {state.current_state} -> {to_state}. "
                f"Allowed: {definition.allowed_transitions}"
            )

        from_state = state.current_state
        state.current_state = to_state
        if event_data:
            state.context.update(event_data)
        await self._store.save_state(state)

        change = StateChangeEvent(
            entity_type=state.entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            event_data=event_data or {},
            trace_id=event_data.get("trace_id") if event_data else None,
        )
        await self._store.append_event(change)
        self._notify(change)
        return change

    async def get_current_state(self, entity_id: str) -> State:
        """Get the current state of an entity."""
        state = await self._store.get_state(entity_id)
        if state is None:
            raise ValueError(f"Entity {entity_id} not found")
        return state

    async def get_state_history(self, entity_id: str) -> list[StateChangeEvent]:
        """Get full event-sourcing history for an entity."""
        return await self._store.get_events(entity_id)

    async def pause(self, entity_id: str, reason: str = "") -> StateChangeEvent:
        """Pause a running entity."""
        return await self.transition(entity_id, "PAUSED", {"reason": reason})

    async def resume(self, entity_id: str, context_update: dict[str, Any] | None = None) -> StateChangeEvent:
        """Resume a paused or waiting entity."""
        return await self.transition(entity_id, "RUNNING", context_update or {})

    def _notify(self, event: StateChangeEvent) -> None:
        for handler in self._on_change:
            try:
                handler(event)
            except Exception:
                logger.exception("State change handler failed for %s", event.event_id)
