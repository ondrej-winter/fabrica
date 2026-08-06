"""Subprocess-backed git adapters for developer workflow use cases."""

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.command_runner import (
    GitCommandResult,
    GitCommandRunner,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.commit import (
    GitCommitSubprocessCreator,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.staged_changes import (
    GitStagedChangesSubprocessLoader,
)

__all__ = [
    "GitCommandResult",
    "GitCommandRunner",
    "GitCommitSubprocessCreator",
    "GitStagedChangesSubprocessLoader",
]
