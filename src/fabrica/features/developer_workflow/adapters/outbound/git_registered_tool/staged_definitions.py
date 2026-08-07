"""Tool definitions for read-only staged git inspection."""

from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import ToolArgumentSchemaValue, ToolDefinition

GIT_STAGED_FILES_TOOL_NAME = "git_staged_files"
GIT_STAGED_DIFF_TOOL_NAME = "git_staged_diff"
GIT_STAGED_FILE_DIFF_TOOL_NAME = "git_staged_file_diff"

_EMPTY_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
_FILE_DIFF_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Relative path of a staged file to inspect. Must be listed by git_staged_files.",
        },
    },
    "required": ("path",),
    "additionalProperties": False,
}

STAGED_GIT_FILES_TOOL_DEFINITION = ToolDefinition(
    name=GIT_STAGED_FILES_TOOL_NAME,
    description="List currently staged git files and their staged statuses.",
    argument_schema=_EMPTY_ARGUMENT_SCHEMA,
)
STAGED_GIT_FULL_DIFF_TOOL_DEFINITION = ToolDefinition(
    name=GIT_STAGED_DIFF_TOOL_NAME,
    description="Return the bounded full staged git diff.",
    argument_schema=_EMPTY_ARGUMENT_SCHEMA,
)
STAGED_GIT_FILE_DIFF_TOOL_DEFINITION = ToolDefinition(
    name=GIT_STAGED_FILE_DIFF_TOOL_NAME,
    description="Return the bounded staged git diff for one staged file path.",
    argument_schema=_FILE_DIFF_ARGUMENT_SCHEMA,
)
