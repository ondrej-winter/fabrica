"""Lease, policy, and approval adapters for apply-patch authorization."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Self

from fabrica.features.workspace_editing.application.dtos import (
    PatchMutationGuarantee,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from fabrica.features.workspace_editing.application.ports import PatchMutationLease


@dataclass(slots=True)
class InProcessPatchMutationLeaseManager:
    """Serialize apply-patch mutation attempts inside one Python process."""

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def acquire(self, *, plan_digest: str | None = None) -> PatchMutationLease:
        """Return an async context manager holding the exclusive mutation lease."""
        return _InProcessPatchMutationLease(self._lock, plan_digest=plan_digest)


@dataclass(slots=True)
class _InProcessPatchMutationLease:
    lock: asyncio.Lock
    plan_digest: str | None = None

    async def __aenter__(self) -> Self:
        await self.lock.acquire()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.lock.release()


@dataclass(frozen=True, slots=True)
class WorkspacePatchPolicyEvaluator:
    """Deny patch plans that touch host-protected workspace paths."""

    protected_prefixes: frozenset[str] = frozenset(
        {".git", ".fabrica/apply-patch/stage", ".fabrica/apply-patch/journal"}
    )

    async def evaluate(self, plan: PatchPlan) -> PatchResult | None:
        """Return a no-mutation rejection when a protected path is touched."""
        for path in _planned_paths(plan):
            if any(_matches_protected_path(path, protected_prefix) for protected_prefix in self.protected_prefixes):
                return _rejected(
                    "PROTECTED_PATH_DENIED",
                    f"apply-patch plan touches protected path: {path}",
                    metadata={"path": path},
                )
        return None


@dataclass(frozen=True, slots=True)
class PatchApprovalDecision:
    """Host decision for one digest-bound immutable patch plan."""

    approved: bool
    plan_digest: str
    reason: str | None = None


type PatchApprovalCallback = Callable[[PatchPlan], Awaitable[PatchApprovalDecision]]


@dataclass(frozen=True, slots=True)
class StaticPatchApprovalRequester:
    """Request host approval and bind the decision to the complete plan digest."""

    approval_callback: PatchApprovalCallback
    timeout_seconds: float | None = 30.0

    async def request_approval(self, plan: PatchPlan) -> PatchResult | None:
        """Return a rejection for unsafe preview, timeout, denial, or stale approval."""
        if plan.approval_preview is None or plan.approval_preview.truncated:
            return _rejected("APPROVAL_DENIED", "apply-patch approval preview is not safe to present")

        try:
            decision = await asyncio.wait_for(self.approval_callback(plan), timeout=self.timeout_seconds)
        except TimeoutError:
            return _rejected("APPROVAL_TIMEOUT", "apply-patch approval timed out")

        if decision.plan_digest != plan.plan_digest:
            return _rejected("STALE_PLAN", "approval decision did not match the immutable plan digest")
        if not decision.approved:
            return _rejected("APPROVAL_DENIED", decision.reason or "apply-patch approval was denied")
        return None


def _planned_paths(plan: PatchPlan) -> tuple[str, ...]:
    paths: list[str] = []
    for action in plan.actions:
        paths.append(action.path)
        if action.destination_path is not None:
            paths.append(action.destination_path)
    paths.extend(directory.path for directory in plan.created_directories)
    paths.extend(step.path for step in plan.commit_steps)
    paths.extend(step.destination_path for step in plan.commit_steps if step.destination_path is not None)
    return tuple(paths)


def _matches_protected_path(path: str, protected_prefix: str) -> bool:
    return path == protected_prefix or path.startswith(f"{protected_prefix}/")


def _rejected(code: str, message: str, *, metadata: dict[str, str] | None = None) -> PatchResult:
    error = patch_error(code, message=message, metadata=metadata)
    return PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        error=error,
    )


__all__ = [
    "InProcessPatchMutationLeaseManager",
    "PatchApprovalDecision",
    "StaticPatchApprovalRequester",
    "WorkspacePatchPolicyEvaluator",
]
