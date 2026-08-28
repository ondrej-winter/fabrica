"""Model-facing registered-tool adapter for workspace reading."""

from fabrica.features.workspace_reading.adapters.inbound.registered_tool.adapter import (
    READ_FILES_TOOL_DEFINITION,
    READ_FILES_TOOL_DESCRIPTION,
    READ_FILES_TOOL_NAME,
    ReadFilesRegisteredToolAdapter,
    create_read_files_registered_tool,
)

__all__ = [
    "READ_FILES_TOOL_DEFINITION",
    "READ_FILES_TOOL_DESCRIPTION",
    "READ_FILES_TOOL_NAME",
    "ReadFilesRegisteredToolAdapter",
    "create_read_files_registered_tool",
]
