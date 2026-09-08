"""Authorization adapters for apply-patch mutation planning."""

from fabrica.features.workspace_editing.adapters.outbound.authorization.adapter import (
    InProcessPatchMutationLeaseManager,
    StaticPatchApprovalRequester,
    WorkspacePatchPolicyEvaluator,
)

__all__ = [
    "InProcessPatchMutationLeaseManager",
    "StaticPatchApprovalRequester",
    "WorkspacePatchPolicyEvaluator",
]
