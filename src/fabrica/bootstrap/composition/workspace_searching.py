"""Composition helpers for explicitly configured workspace-searching tools."""

from pathlib import Path

from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_searching.adapters.inbound.registered_tool import create_search_codebase_registered_tool
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import PinnedRipgrepWorkspaceSearchBackend
from fabrica.features.workspace_searching.application.dtos import SearchLimits
from fabrica.features.workspace_searching.application.use_cases import SearchCodebase


def create_search_codebase_registered_tool_adapter(
    workspace_root: Path,
    *,
    limits: SearchLimits | None = None,
) -> AsyncRegisteredTool:
    """Create the search tool without inspecting the workspace during construction.

    Construction wires immutable configuration and the pinned backend only. Search
    scope resolution, package-data verification, and subprocess execution occur
    only after a model invokes the tool.
    """
    resolved_limits = limits or SearchLimits()
    use_case = SearchCodebase(backend=PinnedRipgrepWorkspaceSearchBackend(workspace_root=workspace_root))
    return create_search_codebase_registered_tool(use_case, limits=resolved_limits)


__all__ = ["create_search_codebase_registered_tool_adapter"]
