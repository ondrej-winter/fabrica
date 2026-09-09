"""Tests for the Codex-backed provider-neutral tool-aware model adapter."""

import asyncio
from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.adapters.outbound.codex_transport_tool_aware_model import (
    CodexTransportToolAwareAgentModel,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    RuntimeObservation,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModelError
from fabrica.features.codex_transport.application.dtos import (
    CodexToolCall,
    CodexToolResult,
    CodexToolTurnCommand,
    CodexToolTurnResult,
    CodexTransportObservation,
    CodexTransportStatus,
)


@dataclass
class FakeTransport:
    result: CodexToolTurnResult
    calls: list[CodexToolTurnCommand] = field(default_factory=list)

    async def run_turn(self, command: CodexToolTurnCommand) -> CodexToolTurnResult:
        self.calls.append(command)
        return self.result


def test_adapter_preserves_tool_call_ids_and_client_managed_tool_results() -> None:
    transport = FakeTransport(
        CodexToolTurnResult(
            status=CodexTransportStatus.SUCCESS,
            tool_calls=(
                CodexToolCall(
                    call_id="call-1",
                    tool_name="read_files",
                    arguments_json='{"path":"README.md"}',
                ),
            ),
        )
    )

    result = asyncio.run(
        CodexTransportToolAwareAgentModel(transport).run_turn(
            LocalAgentRunCommand(prompt="Inspect the repository"),
            available_tools=(ToolDefinition(name="read_files", description="Read files"),),
            tool_results=(
                ToolCallResult(
                    call_id="prior-1",
                    tool_name="search_codebase",
                    status=ToolCallResultStatus.SUCCESS,
                    arguments={"query": "README.md"},
                    result_text='{"matches": []}',
                ),
            ),
        )
    )

    assert result.tool_calls[0].call_id == "call-1"
    assert result.tool_calls[0].arguments == {"path": "README.md"}
    assert transport.calls[0].tools[0].name == "read_files"
    assert transport.calls[0].tool_results[0].call_id == "prior-1"
    assert transport.calls[0].tool_results[0].arguments_json == '{"query":"README.md"}'


def test_adapter_normalizes_json_arrays_for_read_files_tool_calls() -> None:
    transport = FakeTransport(
        CodexToolTurnResult(
            status=CodexTransportStatus.SUCCESS,
            tool_calls=(
                CodexToolCall(
                    call_id="call-1",
                    tool_name="read_files",
                    arguments_json='{"files":[{"path":"README.md"}]}',
                ),
            ),
        ),
    )

    result = asyncio.run(
        CodexTransportToolAwareAgentModel(transport).run_turn(
            LocalAgentRunCommand(prompt="Load the README"),
            available_tools=(ToolDefinition(name="read_files", description="Read files"),),
        ),
    )

    assert result.tool_calls == (
        ToolCallRequest(
            call_id="call-1",
            tool_name="read_files",
            arguments={"files": ({"path": "README.md"},)},
        ),
    )


def test_adapter_forwards_successful_text_content_as_the_codex_tool_output() -> None:
    transport = FakeTransport(CodexToolTurnResult(status=CodexTransportStatus.SUCCESS, output_text="done"))

    asyncio.run(
        CodexTransportToolAwareAgentModel(transport).run_turn(
            LocalAgentRunCommand(prompt="Analyze the README"),
            available_tools=(),
            tool_results=(
                ToolCallResult(
                    call_id="call-1",
                    tool_name="read_files",
                    status=ToolCallResultStatus.SUCCESS,
                    arguments={"files": ({"path": "README.md"},)},
                    content=(ToolTextContent(text='{"content":"README contents","success":true}'),),
                ),
            ),
        ),
    )

    assert transport.calls[0].tool_results == (
        CodexToolResult(
            call_id="call-1",
            tool_name="read_files",
            arguments_json='{"files":[{"path":"README.md"}]}',
            result_text='{"content":"README contents","success":true}',
        ),
    )


def test_adapter_preserves_safe_transport_diagnostics_when_a_tool_turn_fails() -> None:
    transport = FakeTransport(
        CodexToolTurnResult(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            observations=(
                CodexTransportObservation(
                    message="Codex backend returned an unsuccessful response",
                    metadata={"category": "backend_error", "http_status": 404},
                ),
            ),
        ),
    )

    with pytest.raises(ToolAwareAgentModelError) as exc_info:
        asyncio.run(
            CodexTransportToolAwareAgentModel(transport).run_turn(
                LocalAgentRunCommand(prompt="Inspect the repository"),
                available_tools=(),
            ),
        )

    err = exc_info.value
    assert err.category == "transport_error"
    assert err.metadata == {"transport_status": "transport_error"}
    assert err.observations == (
        RuntimeObservation(
            message="Codex backend returned an unsuccessful response",
            metadata={"transport_status": "transport_error", "category": "backend_error", "http_status": 404},
        ),
    )
