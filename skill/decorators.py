from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class IdempotencyBackend(Enum):
    MEMORY = "memory"
    REDIS = "redis"


class _MemoryCache:
    """Thread-safe in-memory cache for idempotency keys."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expiry, result = entry
        if time.monotonic() > expiry:
            del self._store[key]
            return None
        return result

    def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        self._store[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        self._store.clear()


_global_cache = _MemoryCache()


def _compute_input_hash(input_data: dict[str, Any], parameters: dict[str, Any], skill_version: str) -> str:
    """Compute a deterministic hash from skill inputs for idempotency."""
    raw = json.dumps(
        {"input": input_data, "params": parameters, "version": skill_version},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def idempotent(
    ttl: int = 3600,
    cache_backend: str = "memory",
) -> Callable[[F], F]:
    """Decorator that makes a skill execution idempotent via input hashing.

    When applied to a skill's execute method, the decorator computes a
    deterministic hash of (input_data, parameters, skill_version) and caches
    the result. Subsequent calls with identical inputs return the cached result
    within the TTL window, enabling safe retries without side effects.

    Args:
        ttl: Cache TTL in seconds. Default 3600 (1 hour).
        cache_backend: Cache backend — "memory" or "redis".

    Returns:
        Decorated function with idempotency guarantees.

    Example:
        @idempotent(ttl=3600)
        async def execute(self, input_data, parameters, trace_id):
            ...
    """
    # Lazy import to avoid circular dependency
    _redis_client: Any = None

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(
            self: Any,
            input_data: dict[str, Any],
            parameters: dict[str, Any],
            trace_id: str,
        ) -> dict[str, Any]:
            version = getattr(self, "version", "0.0.0")
            input_hash = _compute_input_hash(input_data, parameters, version)

            # Check cache
            if cache_backend == "redis":
                cached = await _redis_get(input_hash) if _redis_client else None
            else:
                cached = _global_cache.get(input_hash)

            if cached is not None:
                logger.info(
                    "Idempotency cache hit | hash=%s skill=%s",
                    input_hash[:12],
                    getattr(self, "name", "unknown"),
                )
                return cached

            # Execute
            result = await func(self, input_data, parameters, trace_id)

            # Cache result
            if cache_backend == "redis":
                if _redis_client:
                    await _redis_set(input_hash, result, ttl)
            else:
                _global_cache.set(input_hash, result, ttl)

            logger.debug(
                "Idempotency cache set | hash=%s ttl=%d",
                input_hash[:12],
                ttl,
            )
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


async def _redis_get(key: str) -> dict[str, Any] | None:
    try:
        import redis.asyncio as aioredis

        client = aioredis.Redis.from_url("redis://localhost:6379/0")
        data = await client.get(f"idempotency:{key}")
        if data:
            return json.loads(data)
    except Exception:
        logger.exception("Redis idempotency cache get failed")
    return None


async def _redis_set(key: str, value: dict[str, Any], ttl: int) -> None:
    try:
        import redis.asyncio as aioredis

        client = aioredis.Redis.from_url("redis://localhost:6379/0")
        await client.setex(f"idempotency:{key}", ttl, json.dumps(value, default=str))
    except Exception:
        logger.exception("Redis idempotency cache set failed")
