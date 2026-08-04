"""Read-only subprocess adapter for staged git changes."""

from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_subprocess.adapter import (
    GitCommandResult,
    GitStagedChangesSubprocessLoader,
)

__all__ = [
    "GitCommandResult",
    "GitStagedChangesSubprocessLoader",
]
