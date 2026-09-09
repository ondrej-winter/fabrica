"""Tests for the Codex-backed provider-neutral tool-aware model adapter."""

import asyncio
from dataclasses import dataclass, field

from fabrica.features.agent_runtime.adapters.outbound.codex_transport_tool_aware_model import (
    CodexTransportToolAwareAgentModel,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
)
from fabrica.features.codex_transport.application.dtos import (
    CodexToolCall,
    CodexToolTurnCommand,
    CodexToolTurnResult,
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
                    result_text='{"matches": []}',
                ),
            ),
        )
    )

    assert result.tool_calls[0].call_id == "call-1"
    assert result.tool_calls[0].arguments == {"path": "README.md"}
    assert transport.calls[0].tools[0].name == "read_files"
    assert transport.calls[0].tool_results[0].call_id == "prior-1"
