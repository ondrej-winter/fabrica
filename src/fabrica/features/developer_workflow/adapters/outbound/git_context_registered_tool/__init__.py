"""Registered-tool bridge for read-only git context inspection."""

from fabrica.features.developer_workflow.adapters.outbound.git_context_registered_tool.adapter import (
    create_git_context_registered_tools,
)

__all__ = ["create_git_context_registered_tools"]
