"""Expose bounded workspace source discovery as one model-facing registered tool."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolDefinition,
    ToolExecutionContext,
    ToolMutationGuarantee,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_searching.application.dtos import (
    DEFAULT_MAX_QUERIES_PER_CALL,
    SearchCodebaseCommand,
    SearchCodebaseResult,
    SearchLimits,
    SearchQuery,
)
from fabrica.features.workspace_searching.application.ports import SearchCodebasePort, WorkspaceSearchContext
from fabrica.features.workspace_searching.application.result_formatting import search_codebase_result_payload

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


@dataclass(frozen=True, slots=True)
class SearchCodebaseRegisteredToolAdapter:
    """Map model arguments to the workspace-searching inbound port."""

    use_case: SearchCodebasePort
    limits: SearchLimits

    async def handle(
        self,
        arguments: Mapping[str, ToolArgumentValue],
        context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        """Validate one request and return its stable structured search result."""
        try:
            command = _command_from_arguments(arguments)
        except (TypeError, ValueError) as err:
            return RegisteredToolOutcome.recoverable_rejection(
                error_code="INVALID_ARGUMENTS",
                error_message=str(err),
            )

        result = await self.use_case.search(
            command,
            WorkspaceSearchContext(
                cancellation=context.cancellation,
                deadline_at=context.phase_deadline(SEARCH_CODEBASE_TOOL_NAME),
                limits=self.limits,
            ),
        )
        return search_codebase_result_to_tool_outcome(result)


def create_search_codebase_registered_tool(
    use_case: SearchCodebasePort,
    *,
    limits: SearchLimits | None = None,
) -> AsyncRegisteredTool:
    """Create the sole model-facing registered tool for workspace searching."""
    adapter = SearchCodebaseRegisteredToolAdapter(use_case=use_case, limits=limits or SearchLimits())
    return AsyncRegisteredTool(definition=SEARCH_CODEBASE_TOOL_DEFINITION, handler=adapter.handle)


def search_codebase_result_to_tool_outcome(result: SearchCodebaseResult) -> RegisteredToolOutcome:
    """Translate a bounded application result to one ordered JSON content part."""
    payload = search_codebase_result_payload(result)
    content = ToolTextContent(text=json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return RegisteredToolOutcome.model_continue_success(
        mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
        content=(content,),
    )


def _command_from_arguments(arguments: Mapping[str, ToolArgumentValue]) -> SearchCodebaseCommand:
    if set(arguments) != {"queries"}:
        msg = "search_codebase requires exactly one queries argument"
        raise ValueError(msg)
    raw_queries = arguments["queries"]
    if isinstance(raw_queries, str):
        return SearchCodebaseCommand((SearchQuery(pattern=raw_queries),))
    if not isinstance(raw_queries, tuple) or not raw_queries:
        msg = "search_codebase requires a non-empty queries array"
        raise ValueError(msg)
    if len(raw_queries) > DEFAULT_MAX_QUERIES_PER_CALL:
        msg = f"search_codebase accepts at most {DEFAULT_MAX_QUERIES_PER_CALL} queries"
        raise ValueError(msg)
    return SearchCodebaseCommand(queries=tuple(_query_from_value(value) for value in raw_queries))


def _query_from_value(value: ToolArgumentValue) -> SearchQuery:
    if isinstance(value, str):
        return SearchQuery(pattern=value)
    if not isinstance(value, Mapping) or not value:
        msg = "each queries entry must be an object or pattern string"
        raise ValueError(msg)
    if set(value) - {"pattern", "path", "glob", "case_sensitive"}:
        msg = "queries entries must not include additional properties"
        raise ValueError(msg)
    pattern = value.get("pattern")
    if not isinstance(pattern, str):
        msg = "each queries entry requires a string pattern"
        raise TypeError(msg)
    path = value.get("path", ".")
    if not isinstance(path, str):
        msg = "query path must be a string"
        raise TypeError(msg)
    glob = value.get("glob")
    if glob is not None and not isinstance(glob, str):
        msg = "query glob must be a string or null"
        raise TypeError(msg)
    case_sensitive = value.get("case_sensitive", False)
    if not isinstance(case_sensitive, bool):
        msg = "query case_sensitive must be a boolean"
        raise TypeError(msg)
    return SearchQuery(pattern=pattern, path=path, glob=glob, case_sensitive=case_sensitive)


__all__ = [
    "SEARCH_CODEBASE_TOOL_DEFINITION",
    "SEARCH_CODEBASE_TOOL_DESCRIPTION",
    "SEARCH_CODEBASE_TOOL_NAME",
    "SearchCodebaseRegisteredToolAdapter",
    "create_search_codebase_registered_tool",
    "search_codebase_result_to_tool_outcome",
]
