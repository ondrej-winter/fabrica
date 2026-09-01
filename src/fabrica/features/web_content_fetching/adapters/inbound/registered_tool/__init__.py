"""Model-facing registered tool adapter for public-web retrieval."""

from fabrica.features.web_content_fetching.adapters.inbound.registered_tool.adapter import (
    FETCH_WEB_CONTENT_TOOL_DEFINITION,
    FETCH_WEB_CONTENT_TOOL_DESCRIPTION,
    FETCH_WEB_CONTENT_TOOL_NAME,
    FetchWebContentRegisteredToolAdapter,
    create_fetch_web_content_registered_tool,
    fetch_web_content_result_to_tool_outcome,
)

__all__ = [
    "FETCH_WEB_CONTENT_TOOL_DEFINITION",
    "FETCH_WEB_CONTENT_TOOL_DESCRIPTION",
    "FETCH_WEB_CONTENT_TOOL_NAME",
    "FetchWebContentRegisteredToolAdapter",
    "create_fetch_web_content_registered_tool",
    "fetch_web_content_result_to_tool_outcome",
]
