from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class RedisAdapter:
    """Redis adapter for distributed caching, locking, and pub/sub.

    Wraps the redis.asyncio client with framework-specific operations.
    """

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        self._url = url
        self._client: Any = None

    async def connect(self) -> None:
        try:
            from redis.asyncio import Redis
        except ImportError:
            raise ImportError("redis is required for RedisAdapter")

        self._client = Redis.from_url(self._url, decode_responses=True)
        await self._client.ping()
        logger.info("Connected to Redis at %s", self._url)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def set_cache(self, key: str, value: dict[str, Any], ttl: int = 3600) -> None:
        if self._client is None:
            raise RuntimeError("Redis not connected")
        await self._client.setex(key, ttl, json.dumps(value, default=str))

    async def get_cache(self, key: str) -> dict[str, Any] | None:
        if self._client is None:
            raise RuntimeError("Redis not connected")
        data = await self._client.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def acquire_lock(
        self, lock_name: str, lock_value: str, ttl: int = 30
    ) -> bool:
        """Acquire a Redis-based distributed lock using SET NX."""
        if self._client is None:
            raise RuntimeError("Redis not connected")
        result = await self._client.set(
            f"lock:{lock_name}", lock_value, nx=True, ex=ttl
        )
        return result is not None

    async def release_lock(self, lock_name: str, lock_value: str) -> bool:
        """Release a lock only if we still hold it (Lua script for atomicity)."""
        if self._client is None:
            raise RuntimeError("Redis not connected")

        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self._client.eval(lua, 1, f"lock:{lock_name}", lock_value)
        return result == 1
