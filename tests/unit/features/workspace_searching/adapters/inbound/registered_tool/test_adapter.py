"""Tests for the model-facing search-codebase registered-tool adapter."""

import asyncio
import json
from asyncio import run
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolArgumentSchemaValue,
    ToolArgumentValue,
    ToolExecutionContext,
    ToolExecutionPhaseDeadline,
    ToolMutationGuarantee,
    ToolOutcomeStatus,
    ToolTextContent,
    canonical_tool_arguments_digest,
)
from fabrica.features.workspace_searching.adapters.inbound.registered_tool import (
    SEARCH_CODEBASE_TOOL_DEFINITION,
    SEARCH_CODEBASE_TOOL_DESCRIPTION,
    SEARCH_CODEBASE_TOOL_NAME,
    SearchCodebaseRegisteredToolAdapter,
    create_search_codebase_registered_tool,
)
from fabrica.features.workspace_searching.application.dtos import (
    DEFAULT_MAX_QUERIES_PER_CALL,
    SearchCodebaseCommand,
    SearchCodebaseResult,
    SearchLimits,
    SearchQuery,
    SearchQuerySuccess,
)
from fabrica.features.workspace_searching.application.ports import WorkspaceSearchContext

PHASE_DEADLINE = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


def test_search_codebase_registered_tool_exposes_only_the_canonical_schema_and_description() -> None:
    tool = create_search_codebase_registered_tool(_FakeSearchCodebase(_result()))

    assert tool.definition == SEARCH_CODEBASE_TOOL_DEFINITION
    assert tool.definition.name == SEARCH_CODEBASE_TOOL_NAME
    schema = cast("dict[str, ToolArgumentSchemaValue]", tool.definition.argument_schema)
    properties = cast("dict[str, ToolArgumentSchemaValue]", schema["properties"])
    queries = cast("dict[str, ToolArgumentSchemaValue]", properties["queries"])
    items = cast("dict[str, ToolArgumentSchemaValue]", queries["items"])
    assert schema["required"] == ("queries",)
    assert schema["additionalProperties"] is False
    assert queries["minItems"] == 1
    assert queries["maxItems"] == DEFAULT_MAX_QUERIES_PER_CALL
    assert items["required"] == ("pattern",)
    assert items["additionalProperties"] is False
    assert SEARCH_CODEBASE_TOOL_DESCRIPTION.startswith("Search file contents across the workspace")
    assert "use read_files for broader context" in SEARCH_CODEBASE_TOOL_DESCRIPTION


def test_search_codebase_registered_tool_maps_canonical_arguments_and_runtime_context() -> None:
    use_case = _FakeSearchCodebase(_result())
    limits = SearchLimits(max_parallel_searches=1)
    adapter = SearchCodebaseRegisteredToolAdapter(use_case=use_case, limits=limits)
    arguments = {
        "queries": (
            {
                "pattern": "UserService",
                "path": "src",
                "glob": "**/*.py",
                "case_sensitive": True,
            },
        )
    }

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command == SearchCodebaseCommand(
        (SearchQuery(pattern="UserService", path="src", glob="**/*.py", case_sensitive=True),)
    )
    assert use_case.context == WorkspaceSearchContext(
        cancellation=_NeverCancelled(),
        deadline_at=PHASE_DEADLINE,
        limits=limits,
    )
    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert outcome.mutation_guarantee is ToolMutationGuarantee.NO_MUTATION
    assert len(outcome.content) == 1
    assert json.loads(_text_part(outcome).text) == {
        "results": [
            {
                "limit_reached": False,
                "matches": [],
                "matches_returned": 0,
                "more_results_possible": False,
                "output_omitted": False,
                "output_truncated": False,
                "query": {"case_sensitive": False, "glob": None, "path": ".", "pattern": "UserService"},
                "reason": None,
                "success": True,
            }
        ]
    }


def test_search_codebase_registered_tool_normalizes_compatibility_patterns_only_at_the_adapter_boundary() -> None:
    use_case = _FakeSearchCodebase(_result())
    adapter = SearchCodebaseRegisteredToolAdapter(use_case=use_case, limits=SearchLimits())
    arguments = {"queries": ("first", "second")}

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command == SearchCodebaseCommand((SearchQuery("first"), SearchQuery("second")))
    assert outcome.status is ToolOutcomeStatus.SUCCESS


def test_search_codebase_registered_tool_normalizes_a_top_level_pattern_string_for_compatibility() -> None:
    use_case = _FakeSearchCodebase(_result())
    adapter = SearchCodebaseRegisteredToolAdapter(use_case=use_case, limits=SearchLimits())
    arguments = {"queries": "UserService"}

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command == SearchCodebaseCommand((SearchQuery("UserService"),))
    assert outcome.status is ToolOutcomeStatus.SUCCESS


def test_search_codebase_registered_tool_rejects_malformed_top_level_arguments_without_executing_the_use_case() -> None:
    use_case = _FakeSearchCodebase(_result())
    adapter = SearchCodebaseRegisteredToolAdapter(use_case=use_case, limits=SearchLimits())
    arguments = {"pattern": "UserService"}

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command is None
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_ARGUMENTS"


@pytest.mark.parametrize(
    "arguments",
    [
        {"queries": ()},
        {"queries": (42,)},
        {"queries": ({"pattern": "needle", "unexpected": True},)},
        {"queries": ({"path": "src"},)},
        {"queries": ({"pattern": "needle", "path": 42},)},
        {"queries": ({"pattern": "needle", "glob": 42},)},
        {"queries": ({"pattern": "needle", "case_sensitive": 1},)},
    ],
)
def test_search_codebase_registered_tool_rejects_malformed_nested_query_arguments(
    arguments: Mapping[str, ToolArgumentValue],
) -> None:
    use_case = _FakeSearchCodebase(_result())
    adapter = SearchCodebaseRegisteredToolAdapter(use_case=use_case, limits=SearchLimits())

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command is None
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_ARGUMENTS"


@dataclass(slots=True)
class _FakeSearchCodebase:
    result: SearchCodebaseResult
    command: SearchCodebaseCommand | None = None
    context: WorkspaceSearchContext | None = None

    async def search(self, command: SearchCodebaseCommand, context: WorkspaceSearchContext) -> SearchCodebaseResult:
        self.command = command
        self.context = context
        return self.result


@dataclass(frozen=True, slots=True)
class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        await asyncio.Event().wait()


def _context(arguments: Mapping[str, ToolArgumentValue]) -> ToolExecutionContext:
    return ToolExecutionContext(
        call_id="call-1",
        argument_digest=canonical_tool_arguments_digest(arguments),
        cancellation=_NeverCancelled(),
        phase_deadlines=(ToolExecutionPhaseDeadline(phase=SEARCH_CODEBASE_TOOL_NAME, deadline_at=PHASE_DEADLINE),),
    )


def _result() -> SearchCodebaseResult:
    return SearchCodebaseResult((SearchQuerySuccess(query=SearchQuery("UserService"), matches=()),))


def _text_part(outcome: RegisteredToolOutcome) -> ToolTextContent:
    content = outcome.content
    assert len(content) == 1
    assert isinstance(content[0], ToolTextContent)
    return content[0]
