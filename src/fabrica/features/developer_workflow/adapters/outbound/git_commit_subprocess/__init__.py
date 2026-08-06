"""Subprocess adapter for approved git commit creation."""

from fabrica.features.developer_workflow.adapters.outbound.git_commit_subprocess.adapter import (
    GitCommitCommandResult,
    GitCommitSubprocessCreator,
)

__all__ = [
    "GitCommitCommandResult",
    "GitCommitSubprocessCreator",
]
