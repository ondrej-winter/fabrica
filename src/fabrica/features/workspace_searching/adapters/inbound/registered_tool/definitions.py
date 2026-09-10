"""Model-facing definitions for workspace source discovery."""

from fabrica.features.agent_runtime.application.dtos import ToolDefinition
from fabrica.features.workspace_searching.application.dtos import DEFAULT_MAX_QUERIES_PER_CALL

SEARCH_CODEBASE_TOOL_NAME = "search_codebase"
SEARCH_CODEBASE_TOOL_DESCRIPTION = """Search file contents across the workspace using regular expressions.

Run multiple independent searches together in one call. Each query may
optionally restrict the search to a workspace-relative path or file glob.

Results contain workspace-relative file paths, one-based line/column
locations, and surrounding context.

Searches are case-insensitive by default. Use case_sensitive when exact
case matters.

Use this tool to locate definitions, references, imports, configuration,
tests, error strings, and other code patterns. After locating relevant
files, use read_files for broader context.

Search output is bounded. If a query reaches the result/output limit,
narrow its regex, path, or glob rather than repeatedly requesting broad
results."""
SEARCH_CODEBASE_TOOL_DEFINITION = ToolDefinition(
    name=SEARCH_CODEBASE_TOOL_NAME,
    description=SEARCH_CODEBASE_TOOL_DESCRIPTION,
    argument_schema={
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "minItems": 1,
                "maxItems": DEFAULT_MAX_QUERIES_PER_CALL,
                "items": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "minLength": 1, "maxLength": 4_000},
                        "path": {"type": "string", "minLength": 1},
                        "glob": {"type": ("string", "null"), "minLength": 1},
                        "case_sensitive": {"type": "boolean"},
                    },
                    "required": ("pattern",),
                    "additionalProperties": False,
                },
            },
        },
        "required": ("queries",),
        "additionalProperties": False,
    },
)


__all__ = [
    "SEARCH_CODEBASE_TOOL_DEFINITION",
    "SEARCH_CODEBASE_TOOL_DESCRIPTION",
    "SEARCH_CODEBASE_TOOL_NAME",
]
