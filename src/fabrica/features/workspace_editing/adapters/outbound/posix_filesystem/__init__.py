"""POSIX filesystem adapters for apply-patch workspace mutation."""

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.adapter import (
    PosixPatchWorkspaceSnapshotAdapter,
)
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.capabilities import (
    PosixPatchCapabilityProbe,
    PosixPatchCapabilityStatus,
    PosixPatchWorkspaceCapabilityEvidence,
    collect_posix_patch_workspace_capability_evidence,
)
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.commit import (
    PosixPatchCommitAdapter,
)
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.journal import (
    PosixPatchJournalAndPreparationAdapter,
)
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.native_operations import (
    NativePatchOperationError,
)

__all__ = [
    "NativePatchOperationError",
    "PosixPatchCapabilityProbe",
    "PosixPatchCapabilityStatus",
    "PosixPatchCommitAdapter",
    "PosixPatchJournalAndPreparationAdapter",
    "PosixPatchWorkspaceCapabilityEvidence",
    "PosixPatchWorkspaceSnapshotAdapter",
    "collect_posix_patch_workspace_capability_evidence",
]
