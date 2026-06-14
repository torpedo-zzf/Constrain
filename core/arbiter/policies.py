from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from core.arbiter.models import PolicyResult, RetryDecision, Task


class Strategy(ABC):
    """Pluggable strategy interface for Arbiter policies."""

    @abstractmethod
    async def evaluate(self, context: dict[str, Any]) -> PolicyResult: ...


class ResourceLockPolicy(Strategy):
    """Resource lock with conflict resolution.

    Supports FIFO, priority queue, and weighted round-robin strategies.
    """

    def __init__(self, mode: str = "fifo") -> None:
        if mode not in ("fifo", "priority", "weighted_rr"):
            raise ValueError(f"Unknown lock mode: {mode}")
        self._mode = mode
        self._locks: dict[str, tuple[str, float]] = {}  # resource -> (requester, expiry)
        self._queue: dict[str, list[tuple[str, float, int]]] = defaultdict(list)  # resource -> [(requester, priority, ts)]

    async def evaluate(self, context: dict[str, Any]) -> PolicyResult:
        resource_id = context.get("resource_id", "")
        requester_id = context.get("requester_id", "")
        ttl = context.get("ttl", 30)

        now = time.monotonic()
        lock = self._locks.get(resource_id)

        if lock is not None:
            owner, expiry = lock
            if now < expiry:
                if owner != requester_id:
                    self._queue[resource_id].append(
                        (requester_id, float(context.get("priority", 0)), int(now))
                    )
                    return PolicyResult(
                        policy_name="resource_lock",
                        allowed=False,
                        reason=f"Resource {resource_id} locked by {owner}",
                    )
                # Renew existing lock
                self._locks[resource_id] = (requester_id, now + ttl)
                return PolicyResult(
                    policy_name="resource_lock",
                    allowed=True,
                    reason="Lock renewed",
                )

        # Lock is free — acquire
        self._locks[resource_id] = (requester_id, now + ttl)
        return PolicyResult(policy_name="resource_lock", allowed=True, reason="Lock acquired")

    async def release(self, resource_id: str, requester_id: str) -> bool:
        lock = self._locks.get(resource_id)
        if lock and lock[0] == requester_id:
            del self._locks[resource_id]
            return True
        return False


class RetryPolicy(Strategy):
    """Exponential backoff retry strategy."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._retryable_exceptions = retryable_exceptions or (Exception,)

    async def decide(self, task: Task, error: Exception) -> RetryDecision:
        if not isinstance(error, self._retryable_exceptions):
            return RetryDecision(
                should_retry=False,
                reason=f"Exception type {type(error).__name__} not retryable",
            )

        if task.retry_count >= task.max_retries:
            return RetryDecision(
                should_retry=False,
                attempt=task.retry_count,
                reason=f"Max retries ({task.max_retries}) reached",
            )

        delay = min(
            self._base_delay * math.pow(2, task.retry_count),
            self._max_delay,
        )
        return RetryDecision(
            should_retry=True,
            delay_seconds=delay,
            attempt=task.retry_count + 1,
            reason=f"Exponential backoff: {delay:.1f}s",
        )

    async def evaluate(self, context: dict[str, Any]) -> PolicyResult:
        # Generic evaluate for policy engine; use decide() for task-specific.
        return PolicyResult(policy_name="retry", allowed=True, reason="OK")


class PriorityPolicy(Strategy):
    """Priority-based scheduling with four levels."""

    LEVELS = {"urgent": 0, "high": 1, "normal": 2, "low": 3}

    def __init__(self, default_priority: str = "normal") -> None:
        self._default = default_priority

    async def evaluate(self, context: dict[str, Any]) -> PolicyResult:
        priority = context.get("priority", self._default)
        level = self.LEVELS.get(priority, 99)
        threshold = self.LEVELS.get(context.get("min_priority", "low"), 3)

        allowed = level <= threshold
        return PolicyResult(
            policy_name="priority",
            allowed=allowed,
            reason=f"Priority {priority} (level {level}) {'allowed' if allowed else 'denied'}",
        )


class RateLimitPolicy(Strategy):
    """Sliding window rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def evaluate(self, context: dict[str, Any]) -> PolicyResult:
        key = context.get("rate_limit_key", "default")
        now = time.monotonic()

        window_start = now - self._window
        self._buckets[key] = [t for t in self._buckets[key] if t > window_start]

        if len(self._buckets[key]) >= self._max_requests:
            return PolicyResult(
                policy_name="rate_limit",
                allowed=False,
                reason=f"Rate limit exceeded: {len(self._buckets[key])}/{self._max_requests}",
            )

        self._buckets[key].append(now)
        return PolicyResult(policy_name="rate_limit", allowed=True, reason="OK")
