"""Authorization adapters for apply-patch mutation planning."""

from fabrica.features.workspace_editing.adapters.outbound.authorization.adapter import (
    InProcessPatchMutationLeaseManager,
    PatchApprovalDecision,
    StaticPatchApprovalRequester,
    WorkspacePatchPolicyEvaluator,
)

__all__ = [
    "InProcessPatchMutationLeaseManager",
    "PatchApprovalDecision",
    "StaticPatchApprovalRequester",
    "WorkspacePatchPolicyEvaluator",
]
