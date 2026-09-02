"""Application-owned ports for safe apply-patch workspace mutation."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

    from fabrica.features.workspace_editing.application.dtos import PatchAction, PatchPlan, PatchResult
    from fabrica.features.workspace_editing.application.dtos.recovery import (
        PatchJournalRecord,
        PatchJournalState,
        PatchRecoveryDecision,
    )
    from fabrica.features.workspace_editing.application.text_snapshot import PatchTextSnapshot
    from fabrica.features.workspace_editing.application.use_cases.plan_patch import PatchPlanningSnapshot


class PatchMutationLease(AbstractAsyncContextManager["PatchMutationLease"], Protocol):
    """Exclusive workspace mutation lease held across planning through cleanup."""


class PatchMutationLeaseManager(Protocol):
    """Outbound port for serializing apply-patch calls for one workspace."""

    def acquire(self, *, plan_digest: str | None = None) -> PatchMutationLease:
        """Acquire the exclusive workspace mutation lease."""
        ...


class PatchClock(Protocol):
    """Outbound port for deterministic patch deadlines and timestamps."""

    def now(self) -> datetime:
        """Return the current timezone-aware timestamp."""
        ...


class PatchWorkspaceSnapshotReader(Protocol):
    """Outbound port for capability checks and immutable workspace snapshots."""

    async def verify_workspace_capabilities(self) -> PatchResult | None:
        """Return a rejection when this workspace cannot provide v1 filesystem guarantees."""
        ...

    async def snapshot_plan_inputs(self, plan: PatchPlan) -> PatchResult | None:
        """Snapshot and validate plan inputs without mutating the workspace."""
        ...

    async def snapshot_for_planning(self, actions: tuple[PatchAction, ...]) -> PatchPlanningSnapshot | PatchResult:
        """Return planning evidence for parsed actions or a no-mutation rejection."""
        ...

    async def read_text_snapshot(self, path: str) -> PatchTextSnapshot | PatchResult:
        """Return decoded immutable text for an existing patch source file."""
        ...


class PatchPolicyEvaluator(Protocol):
    """Outbound port for host-owned immutable plan policy decisions."""

    async def evaluate(self, plan: PatchPlan) -> PatchResult | None:
        """Return a rejection when policy denies the plan; otherwise return None."""
        ...


class PatchApprovalRequester(Protocol):
    """Outbound port for approval of an immutable, already-policy-checked plan."""

    async def request_approval(self, plan: PatchPlan) -> PatchResult | None:
        """Return a rejection when approval is denied, timed out, or preview is unsafe."""
        ...


class PatchJournalStore(Protocol):
    """Outbound port for durable journal recording and startup discovery."""

    async def list_incomplete(self) -> tuple[PatchJournalRecord, ...]:
        """List incomplete journals that gate workspace mutation exposure."""
        ...

    async def create(self, plan: PatchPlan) -> PatchJournalRecord:
        """Durably record recovery intent before visible preparation effects."""
        ...

    async def transition(self, record: PatchJournalRecord, destination: PatchJournalState) -> PatchJournalRecord:
        """Durably advance a journal through a legal lifecycle transition."""
        ...


class PatchStager(Protocol):
    """Outbound port for reversible preparation and staged file artifacts."""

    async def prepare(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Create journaled preparation effects and staged artifacts before file commit."""
        ...


class PatchCommitter(Protocol):
    """Outbound port for deterministic file commit and bounded rollback."""

    async def commit(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult:
        """Cross the file commit point and return the terminal mutation result."""
        ...

    async def roll_back(self, journal: PatchJournalRecord) -> PatchResult:
        """Roll back journaled visible effects when identity evidence proves it safe."""
        ...


class PatchRecoveryCoordinator(Protocol):
    """Outbound port for startup recovery over incomplete durable journals."""

    async def inspect(self, journal: PatchJournalRecord) -> PatchRecoveryDecision:
        """Decide whether an incomplete journal is clean, rollback-safe, or operator-gated."""
        ...

    async def recover(self, journal: PatchJournalRecord) -> PatchResult:
        """Perform safe startup recovery or return a fatal recovery-required result."""
        ...


class PatchCleanupStack(Protocol):
    """Application-visible cleanup stack for cancellation-safe adapter resources."""

    def push_async_callback(self, callback: AbstractAsyncContextManager[object]) -> None:
        """Register adapter-owned cleanup without exposing OS handles to the application."""
        ...

    async def aclose(self) -> None:
        """Run registered cleanup before reporting a terminal patch result."""
        ...


class PatchAsyncResource(Protocol):
    """Factory for adapter-owned async resource scopes used by patch phases."""

    def open(self) -> AsyncIterator[object]:
        """Open a resource scope without exposing concrete infrastructure details."""
        ...


__all__ = [
    "PatchApprovalRequester",
    "PatchAsyncResource",
    "PatchCleanupStack",
    "PatchClock",
    "PatchCommitter",
    "PatchJournalStore",
    "PatchMutationLease",
    "PatchMutationLeaseManager",
    "PatchPolicyEvaluator",
    "PatchRecoveryCoordinator",
    "PatchStager",
    "PatchWorkspaceSnapshotReader",
]
