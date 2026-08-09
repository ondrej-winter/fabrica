"""Tool definitions for explicit pre-commit execution."""

from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import ToolArgumentSchemaValue, ToolDefinition

RUN_PRE_COMMIT_TOOL_NAME = "run_pre_commit"

RUN_PRE_COMMIT_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "hook_id": {
            "type": "string",
            "description": "Optional pre-commit hook id to run. Must not be a flag or shell expression.",
        },
        "all_files": {
            "type": "boolean",
            "description": "When true, run against all files using --all-files. Defaults to false.",
        },
    },
    "additionalProperties": False,
}

RUN_PRE_COMMIT_TOOL_DEFINITION = ToolDefinition(
    name=RUN_PRE_COMMIT_TOOL_NAME,
    description="Run explicitly composed pre-commit hooks. This may modify files or pre-commit caches.",
    argument_schema=RUN_PRE_COMMIT_ARGUMENT_SCHEMA,
)
