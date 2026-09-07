"""Tests for the model-facing fetch-web-content registered-tool adapter."""

import asyncio
import json
from asyncio import run
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    MAX_TOOL_CONTENT_PARTS,
    MAX_TOOL_CONTENT_TEXT_CHARS,
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
from fabrica.features.web_content_fetching.adapters.inbound.registered_tool import (
    FETCH_WEB_CONTENT_TOOL_DEFINITION,
    FETCH_WEB_CONTENT_TOOL_DESCRIPTION,
    FETCH_WEB_CONTENT_TOOL_NAME,
    FetchWebContentRegisteredToolAdapter,
    create_fetch_web_content_registered_tool,
    fetch_web_content_result_to_tool_outcome,
)
from fabrica.features.web_content_fetching.application.dtos import (
    DEFAULT_MAX_CONTENT_CHARS,
    DEFAULT_MAX_REQUESTS_PER_CALL,
    MIN_REQUEST_CONTENT_CHARS,
    FetchContentFormat,
    FetchSuccess,
    FetchWebContentCommand,
    FetchWebContentLimits,
    FetchWebContentRequest,
    FetchWebContentResult,
)
from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext

PHASE_DEADLINE = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
EXPECTED_MULTIPART_CONTENT_COUNT = 2


def test_fetch_web_content_registered_tool_exposes_only_the_canonical_schema_and_description() -> None:
    tool = create_fetch_web_content_registered_tool(
        _FakeFetchWebContent(_result()),
        public_web_enabled=False,
    )

    assert tool.definition == FETCH_WEB_CONTENT_TOOL_DEFINITION
    assert tool.definition.name == FETCH_WEB_CONTENT_TOOL_NAME
    schema = cast("dict[str, ToolArgumentSchemaValue]", tool.definition.argument_schema)
    properties = cast("dict[str, ToolArgumentSchemaValue]", schema["properties"])
    requests = cast("dict[str, ToolArgumentSchemaValue]", properties["requests"])
    items = cast("dict[str, ToolArgumentSchemaValue]", requests["items"])
    item_properties = cast("dict[str, ToolArgumentSchemaValue]", items["properties"])
    max_chars = cast("dict[str, ToolArgumentSchemaValue]", item_properties["max_chars"])
    assert schema["required"] == ("requests",)
    assert schema["additionalProperties"] is False
    assert requests["minItems"] == 1
    assert requests["maxItems"] == DEFAULT_MAX_REQUESTS_PER_CALL
    assert items["required"] == ("url",)
    assert items["additionalProperties"] is False
    assert max_chars["minimum"] == MIN_REQUEST_CONTENT_CHARS
    assert max_chars["maximum"] == DEFAULT_MAX_CONTENT_CHARS
    assert "untrusted web data" in FETCH_WEB_CONTENT_TOOL_DESCRIPTION
    assert "headers" in FETCH_WEB_CONTENT_TOOL_DESCRIPTION


def test_fetch_web_content_registered_tool_maps_arguments_and_runtime_context() -> None:
    use_case = _FakeFetchWebContent(_result())
    limits = FetchWebContentLimits(max_parallel_fetches=1)
    adapter = FetchWebContentRegisteredToolAdapter(use_case=use_case, limits=limits, public_web_enabled=True)
    arguments = {"requests": ({"url": "https://example.com/page", "max_chars": 2_000},)}

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command == FetchWebContentCommand((FetchWebContentRequest("https://example.com/page", 2_000),))
    assert use_case.context == FetchWebContentContext(
        public_web_enabled=True,
        cancellation=_NeverCancelled(),
        deadline_at=PHASE_DEADLINE,
        limits=limits,
    )
    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert outcome.mutation_guarantee is ToolMutationGuarantee.NO_MUTATION
    assert json.loads(_joined_text(outcome)) == {
        "batch_content_truncated": False,
        "results": [
            {
                "content": "hello",
                "content_chars": 5,
                "content_format": "text",
                "content_type": "text/plain",
                "final_url": "https://example.com/page",
                "media_type": "text/plain",
                "redirects": [],
                "requested_url": "https://example.com/page",
                "returned_chars": 5,
                "size_bytes": 5,
                "status": 200,
                "success": True,
                "trust": "untrusted_web_content",
                "truncated": False,
            }
        ],
    }


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"requests": ()},
        {"requests": ({"url": "https://example.com", "headers": {}},)},
        {"requests": ({"max_chars": 2_000},)},
        {"requests": ({"url": 42},)},
        {"requests": ({"url": "https://example.com", "max_chars": True},)},
    ],
)
def test_fetch_web_content_registered_tool_rejects_invalid_arguments(
    arguments: Mapping[str, ToolArgumentValue],
) -> None:
    use_case = _FakeFetchWebContent(_result())
    adapter = FetchWebContentRegisteredToolAdapter(
        use_case=use_case,
        limits=FetchWebContentLimits(),
        public_web_enabled=True,
    )

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command is None
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_ARGUMENTS"


def test_fetch_web_content_registered_tool_rejects_too_many_or_non_object_requests() -> None:
    for arguments in (
        {"requests": tuple({"url": f"https://{index}.example"} for index in range(9))},
        {"requests": ("not-an-object",)},
    ):
        adapter = FetchWebContentRegisteredToolAdapter(
            use_case=_FakeFetchWebContent(_result()),
            limits=FetchWebContentLimits(),
            public_web_enabled=True,
        )

        outcome = run(adapter.handle(arguments, _context(arguments)))

        assert outcome.error_code == "INVALID_ARGUMENTS"


def test_fetch_web_content_result_serialization_chunks_without_losing_fields() -> None:
    content = "x" * (MAX_TOOL_CONTENT_TEXT_CHARS + 1)
    result = FetchWebContentResult((_success(content),))

    outcome = fetch_web_content_result_to_tool_outcome(result)

    assert len(outcome.content) == EXPECTED_MULTIPART_CONTENT_COUNT
    assert all(isinstance(part, ToolTextContent) for part in outcome.content)
    text_parts = tuple(part for part in outcome.content if isinstance(part, ToolTextContent))
    assert all(len(part.text) <= MAX_TOOL_CONTENT_TEXT_CHARS for part in text_parts)
    payload = json.loads(_joined_text(outcome))
    assert payload["results"][0]["content"] == content
    assert payload["results"][0]["trust"] == "untrusted_web_content"


def test_fetch_web_content_result_rejects_payloads_exceeding_runtime_part_bound() -> None:
    content = "x" * (MAX_TOOL_CONTENT_TEXT_CHARS * (MAX_TOOL_CONTENT_PARTS + 1))

    with pytest.raises(ValueError, match="multipart bounds"):
        fetch_web_content_result_to_tool_outcome(FetchWebContentResult((_success(content),)))


@dataclass(slots=True)
class _FakeFetchWebContent:
    result: FetchWebContentResult
    command: FetchWebContentCommand | None = None
    context: FetchWebContentContext | None = None

    async def fetch(self, command: FetchWebContentCommand, context: FetchWebContentContext) -> FetchWebContentResult:
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
        phase_deadlines=(ToolExecutionPhaseDeadline(phase=FETCH_WEB_CONTENT_TOOL_NAME, deadline_at=PHASE_DEADLINE),),
    )


def _result() -> FetchWebContentResult:
    return FetchWebContentResult((_success("hello"),))


def _success(content: str) -> FetchSuccess:
    return FetchSuccess(
        requested_url="https://example.com/page",
        final_url="https://example.com/page",
        status=200,
        content_type="text/plain",
        media_type="text/plain",
        size_bytes=len(content),
        content_format=FetchContentFormat.TEXT,
        content=content,
        content_chars=len(content),
        returned_chars=len(content),
        truncated=False,
    )


def _joined_text(outcome: RegisteredToolOutcome) -> str:
    return "".join(part.text for part in outcome.content if isinstance(part, ToolTextContent))
