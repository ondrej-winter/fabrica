"""POSIX filesystem adapters for apply-patch workspace mutation."""

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.adapter import (
    PosixPatchWorkspaceSnapshotAdapter,
)
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.commit import (
    PosixPatchCommitAdapter,
)
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.journal import (
    PosixPatchJournalAndPreparationAdapter,
)

__all__ = [
    "PosixPatchCommitAdapter",
    "PosixPatchJournalAndPreparationAdapter",
    "PosixPatchWorkspaceSnapshotAdapter",
]
