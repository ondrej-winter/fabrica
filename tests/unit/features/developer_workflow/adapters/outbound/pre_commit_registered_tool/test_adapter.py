"""Tests for the explicit pre-commit registered-tool bridge."""

from dataclasses import dataclass, field
from typing import cast

import pytest

from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredToolExecutor
from fabrica.features.agent_runtime.application.dtos import (
    ToolArgumentSchemaValue,
    ToolCallRequest,
    ToolCallResultStatus,
    ToolLoopLimits,
)
from fabrica.features.developer_workflow.adapters.outbound.pre_commit_registered_tool import (
    create_pre_commit_registered_tools,
)
from fabrica.features.developer_workflow.application.dtos import (
    PreCommitFailureCategory,
    PreCommitRunCommand,
    PreCommitRunResult,
    PreCommitRunStatus,
)
from fabrica.features.developer_workflow.application.ports import PreCommitRunError


@dataclass
class FakePreCommitPort:
    result: PreCommitRunResult = field(
        default_factory=lambda: PreCommitRunResult(
            status=PreCommitRunStatus.PASSED,
            stdout="passed\n",
            returncode=0,
            metadata={"duration_seconds": 0.123456},
        ),
    )
    error: PreCommitRunError | None = None
    commands: list[PreCommitRunCommand] = field(default_factory=list)

    def run_pre_commit(self, command: PreCommitRunCommand) -> PreCommitRunResult:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.result


def test_factory_creates_exact_pre_commit_tool_definition() -> None:
    tools = create_pre_commit_registered_tools(FakePreCommitPort())

    assert len(tools) == 1
    definition = tools[0].definition
    properties = cast("dict[str, ToolArgumentSchemaValue]", definition.argument_schema["properties"])
    assert definition.name == "run_pre_commit"
    assert definition.argument_schema["additionalProperties"] is False
    assert set(properties) == {"hook_id", "all_files"}
    assert "modify files" in definition.description


def test_handler_maps_arguments_to_pre_commit_command_and_formats_result() -> None:
    port = FakePreCommitPort()
    tool = create_pre_commit_registered_tools(port)[0]

    output = tool.handler({"hook_id": "ruff", "all_files": True})

    assert port.commands == [PreCommitRunCommand(hook_id="ruff", all_files=True)]
    assert "status\tpassed" in output
    assert "returncode\t0" in output
    assert "stdout\npassed" in output
    assert "side_effects\tpre-commit hooks may modify files or caches" in output


def test_handler_rejects_arbitrary_arguments() -> None:
    tool = create_pre_commit_registered_tools(FakePreCommitPort())[0]

    with pytest.raises(ValueError, match="unsupported"):
        tool.handler({"args": "--all-files"})


def test_handler_maps_port_failures_to_safe_tool_failure() -> None:
    tool = create_pre_commit_registered_tools(
        FakePreCommitPort(
            error=PreCommitRunError(
                "pre-commit failed",
                category=PreCommitFailureCategory.EXECUTION_FAILED,
                metadata={"secret": "not surfaced"},
            )
        )
    )[0]

    result = RegisteredToolExecutor((tool,)).execute_tool(
        ToolCallRequest(call_id="call-1", tool_name="run_pre_commit", arguments={}),
        ToolLoopLimits(),
    )

    assert result.status is ToolCallResultStatus.TOOL_FAILURE
    assert result.error_message == "registered tool execution failed"
    assert "not surfaced" not in str(result)
