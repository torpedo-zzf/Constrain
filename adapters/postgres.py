from __future__ import annotations

import json
import logging
from typing import Any

from core.state_machine.models import State, StateChangeEvent, StateStore

logger = logging.getLogger(__name__)


class PostgresStateStore(StateStore):
    """PostgreSQL-backed state store for the StateMachine.

    Requires asyncpg. Stores state as JSONB rows and events
    as append-only event log for event sourcing.
    """

    def __init__(self, dsn: str = "postgresql://user:pass@localhost:5432/constrain") -> None:
        self._dsn = dsn
        self._pool: Any = None

    async def connect(self) -> None:
        try:
            import asyncpg
        except ImportError:
            raise ImportError("asyncpg is required for PostgresStateStore")

        self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)

        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS state_machine_states (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    current_state TEXT NOT NULL,
                    context JSONB NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS state_machine_events (
                    event_id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    event_data JSONB NOT NULL DEFAULT '{}',
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    trace_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_sm_events_entity
                    ON state_machine_events(entity_id, timestamp);
            """)
        logger.info("Connected to PostgreSQL at %s", self._dsn)

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def save_state(self, state: State) -> None:
        if self._pool is None:
            raise RuntimeError("PostgreSQL not connected")
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO state_machine_states (entity_id, entity_type, current_state, context, updated_at)
                VALUES ($1, $2, $3, $4::jsonb, NOW())
                ON CONFLICT (entity_id)
                DO UPDATE SET current_state = $3, context = $4::jsonb, updated_at = NOW()
                """,
                state.entity_id,
                state.entity_type,
                state.current_state,
                json.dumps(state.context, default=str),
            )

    async def get_state(self, entity_id: str) -> State | None:
        if self._pool is None:
            raise RuntimeError("PostgreSQL not connected")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM state_machine_states WHERE entity_id = $1", entity_id
            )
        if row is None:
            return None
        return State(
            entity_id=row["entity_id"],
            entity_type=row["entity_type"],
            current_state=row["current_state"],
            context=row["context"],
            updated_at=row["updated_at"],
        )

    async def append_event(self, event: StateChangeEvent) -> None:
        if self._pool is None:
            raise RuntimeError("PostgreSQL not connected")
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO state_machine_events
                    (event_id, entity_id, entity_type, from_state, to_state, event_data, timestamp, trace_id)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
                ON CONFLICT (event_id) DO NOTHING
                """,
                event.event_id,
                event.entity_id,
                event.entity_type,
                event.from_state,
                event.to_state,
                json.dumps(event.event_data, default=str),
                event.timestamp,
                event.trace_id,
            )

    async def get_events(self, entity_id: str) -> list[StateChangeEvent]:
        if self._pool is None:
            raise RuntimeError("PostgreSQL not connected")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM state_machine_events WHERE entity_id = $1 ORDER BY timestamp",
                entity_id,
            )
        return [
            StateChangeEvent(
                event_id=r["event_id"],
                entity_id=r["entity_id"],
                entity_type=r["entity_type"],
                from_state=r["from_state"],
                to_state=r["to_state"],
                event_data=r["event_data"],
                timestamp=r["timestamp"],
                trace_id=r.get("trace_id"),
            )
            for r in rows
        ]
