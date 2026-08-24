"""Application-owned ports for workspace editing."""

from fabrica.features.workspace_editing.application.ports.workspace_mutation import (
    PatchApprovalRequester,
    PatchAsyncResource,
    PatchCancellationSignal,
    PatchCleanupStack,
    PatchClock,
    PatchCommitter,
    PatchJournalStore,
    PatchMutationLease,
    PatchMutationLeaseManager,
    PatchPolicyEvaluator,
    PatchRecoveryCoordinator,
    PatchStager,
    PatchWorkspaceSnapshotReader,
)

__all__ = [
    "PatchApprovalRequester",
    "PatchAsyncResource",
    "PatchCancellationSignal",
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
