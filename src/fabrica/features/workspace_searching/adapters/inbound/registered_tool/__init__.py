"""Model-facing registered-tool adapter for workspace searching."""

from fabrica.features.workspace_searching.adapters.inbound.registered_tool.adapter import (
    SearchCodebaseRegisteredToolAdapter,
    create_search_codebase_registered_tool,
)
from fabrica.features.workspace_searching.adapters.inbound.registered_tool.definitions import (
    SEARCH_CODEBASE_TOOL_DEFINITION,
    SEARCH_CODEBASE_TOOL_DESCRIPTION,
    SEARCH_CODEBASE_TOOL_NAME,
)

__all__ = [
    "SEARCH_CODEBASE_TOOL_DEFINITION",
    "SEARCH_CODEBASE_TOOL_DESCRIPTION",
    "SEARCH_CODEBASE_TOOL_NAME",
    "SearchCodebaseRegisteredToolAdapter",
    "create_search_codebase_registered_tool",
]
