"""Model-facing registered-tool adapter for workspace searching."""

from fabrica.features.workspace_searching.adapters.inbound.registered_tool.adapter import (
    SEARCH_CODEBASE_TOOL_DEFINITION,
    SEARCH_CODEBASE_TOOL_DESCRIPTION,
    SEARCH_CODEBASE_TOOL_NAME,
    SearchCodebaseRegisteredToolAdapter,
    create_search_codebase_registered_tool,
)

__all__ = [
    "SEARCH_CODEBASE_TOOL_DEFINITION",
    "SEARCH_CODEBASE_TOOL_DESCRIPTION",
    "SEARCH_CODEBASE_TOOL_NAME",
    "SearchCodebaseRegisteredToolAdapter",
    "create_search_codebase_registered_tool",
]
