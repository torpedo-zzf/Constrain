from __future__ import annotations

import logging
from typing import Any

from core.arbiter.models import AuditRecord, LockResult, LockStatus, PolicyResult, RetryDecision, Task
from core.arbiter.policies import (
    PriorityPolicy,
    RateLimitPolicy,
    ResourceLockPolicy,
    RetryPolicy,
    Strategy,
)

logger = logging.getLogger(__name__)


class Arbiter:
    """Central decision engine for resource allocation, conflict resolution, and policy enforcement.

    All decisions are recorded in an immutable audit trail.
    Supports plugin-based strategy injection and hot-reloadable policy configuration.
    """

    def __init__(
        self,
        lock_policy: ResourceLockPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        priority_policy: PriorityPolicy | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
    ) -> None:
        self._lock_policy = lock_policy or ResourceLockPolicy()
        self._retry_policy = retry_policy or RetryPolicy()
        self._priority_policy = priority_policy or PriorityPolicy()
        self._rate_limit_policy = rate_limit_policy or RateLimitPolicy()
        self._custom_policies: dict[str, Strategy] = {}
        self._audit_log: list[AuditRecord] = []
        self._cache: dict[str, Any] = {}

    # --- Resource Lock ---

    async def acquire_lock(self, resource_id: str, requester_id: str, ttl: int = 30) -> LockResult:
        """Attempt to acquire a distributed lock on a resource."""
        result = await self._lock_policy.evaluate({
            "resource_id": resource_id,
            "requester_id": requester_id,
            "ttl": ttl,
        })
        status = LockStatus.ACQUIRED if result.allowed else LockStatus.DENIED
        lock_result = LockResult(
            resource_id=resource_id,
            requester_id=requester_id,
            status=status,
            ttl=ttl,
            reason=result.reason,
        )
        self._audit("acquire_lock", requester_id, resource_id, status.value, result.reason)
        return lock_result

    async def release_lock(self, resource_id: str, requester_id: str) -> bool:
        """Release a previously acquired lock."""
        released = await self._lock_policy.release(resource_id, requester_id)
        if released:
            self._audit("release_lock", requester_id, resource_id, "released", "OK")
        return released

    async def renew_lock(self, resource_id: str, requester_id: str, ttl: int = 30) -> LockResult:
        """Renew an existing lock."""
        return await self.acquire_lock(resource_id, requester_id, ttl)

    # --- Retry Decision ---

    async def decide_retry(self, task: Task, error: Exception) -> RetryDecision:
        """Decide whether and when to retry a failed task."""
        return await self._retry_policy.decide(task, error)

    # --- Policy Evaluation ---

    async def evaluate_policy(self, policy_name: str, context: dict[str, Any]) -> PolicyResult:
        """Evaluate a named policy against the given context.

        Supports built-in policies and registered custom strategies.
        """
        policy_map: dict[str, Strategy] = {
            "resource_lock": self._lock_policy,
            "retry": self._retry_policy,
            "priority": self._priority_policy,
            "rate_limit": self._rate_limit_policy,
            **self._custom_policies,
        }

        policy = policy_map.get(policy_name)
        if policy is None:
            return PolicyResult(
                policy_name=policy_name,
                allowed=False,
                reason=f"Unknown policy: {policy_name}",
            )

        result = await policy.evaluate(context)
        self._audit("evaluate_policy", policy_name, policy_name, "allowed" if result.allowed else "denied", result.reason)
        return result

    def register_policy(self, name: str, strategy: Strategy) -> None:
        """Register a custom strategy as a named policy."""
        self._custom_policies[name] = strategy

    # --- Configuration ---

    def update_config(self, config: dict[str, Any]) -> None:
        """Hot-reload policy configurations from a dict."""
        if "retry" in config:
            rc = config["retry"]
            self._retry_policy = RetryPolicy(
                max_retries=rc.get("max_retries", 3),
                base_delay=rc.get("base_delay", 1.0),
                max_delay=rc.get("max_delay", 60.0),
            )
        if "rate_limit" in config:
            rlc = config["rate_limit"]
            self._rate_limit_policy = RateLimitPolicy(
                max_requests=rlc.get("max_requests", 100),
                window_seconds=rlc.get("window", 60),
            )

    # --- Audit ---

    def get_audit_log(
        self,
        limit: int = 100,
        action: str | None = None,
    ) -> list[AuditRecord]:
        """Retrieve the decision audit trail.

        Args:
            limit: Maximum number of records to return.
            action: Optional filter by action type.

        Returns:
            Chronological list of audit records.
        """
        records = self._audit_log
        if action:
            records = [r for r in records if r.action == action]
        return records[-limit:]

    def _audit(self, action: str, requester: str, resource: str, decision: str, reason: str) -> None:
        record = AuditRecord(
            action=action,
            requester=requester,
            resource=resource,
            decision=decision,
            reason=reason,
        )
        self._audit_log.append(record)
        logger.debug(
            "Arbiter | %s | %s on %s by %s -> %s: %s",
            record.record_id[:8],
            action,
            resource,
            requester,
            decision,
            reason,
        )
