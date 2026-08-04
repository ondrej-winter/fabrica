"""Registered tools for read-only staged git changes."""

from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_registered_tool.adapter import (
    create_git_staged_changes_registered_tools,
)

__all__ = ["create_git_staged_changes_registered_tools"]
