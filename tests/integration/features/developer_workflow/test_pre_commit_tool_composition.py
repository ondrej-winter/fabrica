"""Offline integration tests for optional mutating pre-commit tool composition."""

from fabrica.bootstrap.composition import (
    PreCommitToolOptions,
    create_pre_commit_registered_tool_adapters,
    create_tool_loop_runtime,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallResult,
    ToolDefinition,
)


class PreCommitToolAwareModel:
    """Fake model that records explicitly exposed pre-commit tools."""

    def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
    ) -> ToolAwareModelResponse:
        """Return without requesting tools; composition exposure is asserted directly."""
        del command, available_tools, tool_results
        return ToolAwareModelResponse(output_text="unused")


def test_pre_commit_tool_helper_returns_exact_optional_tool_without_running_hooks() -> None:
    tools = create_pre_commit_registered_tool_adapters(PreCommitToolOptions(timeout_seconds=1.0))

    assert tuple(tool.definition.name for tool in tools) == ("run_pre_commit",)


def test_pre_commit_tools_are_exposed_only_when_explicitly_supplied() -> None:
    tools = create_pre_commit_registered_tool_adapters()
    runtime = create_tool_loop_runtime(model=PreCommitToolAwareModel(), tools=tools)
    empty_runtime = create_tool_loop_runtime(model=PreCommitToolAwareModel(), tools=())

    assert tuple(tool.name for tool in runtime.available_tools) == ("run_pre_commit",)
    assert empty_runtime.available_tools == ()
