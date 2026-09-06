"""Offline integration tests for explicit run-commands tool-loop composition."""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from fabrica.bootstrap import (
    RunCommandsToolOptions,
    create_run_commands_registered_tool_adapter,
    create_tool_loop_runtime,
)
from fabrica.bootstrap.composition import workspace_command_execution
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolCallRequest,
    ToolLoopLimits,
    ToolLoopRunStatus,
    ToolTextContent,
)
from fabrica.features.workspace_command_execution.adapters.inbound.registered_tool import RUN_COMMANDS_TOOL_NAME
from fabrica.features.workspace_command_execution.application.dtos import CommandExecutionLimits, PlannedCommand
from fabrica.features.workspace_command_execution.application.ports import CommandPermissionDecision
from tests.integration.support.agent_runtime_tool_loop import SingleToolCallThenFinalModel

EXPECTED_TOOL_LOOP_TURN_COUNT = 2


@dataclass(slots=True)
class ExplicitHostPolicies:
    """Record policy calls so composition can prove construction is inert."""

    environment_calls: int = 0
    permission_calls: int = 0
    approval_calls: int = 0
    sandbox_calls: int = 0

    def build_environment(self, requested_overrides: dict[str, str]) -> dict[str, str]:
        self.environment_calls += 1
        assert requested_overrides == {}
        return {}

    async def evaluate(self, command: PlannedCommand) -> CommandPermissionDecision:
        self.permission_calls += 1
        assert command.index == 0
        return CommandPermissionDecision.ALLOW

    async def resolve(self, command: PlannedCommand) -> bool:
        self.approval_calls += 1
        assert command.index == 0
        return True

    async def allow(self, command: PlannedCommand) -> bool:
        self.sandbox_calls += 1
        assert command.index == 0
        return True


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="default supervisor targets macOS/Linux")
def test_run_commands_factory_composes_an_explicit_tool_loop_without_side_effects_on_construction(
    tmp_path: Path,
) -> None:
    """Defer workspace inspection, policy evaluation, and execution until invocation."""
    policies = ExplicitHostPolicies()
    model = SingleToolCallThenFinalModel(
        ToolCallRequest(
            call_id="call-1",
            tool_name=RUN_COMMANDS_TOOL_NAME,
            arguments={"commands": ({"argv": (sys.executable, "-c", "print('composed')")},)},
        )
    )

    tool = create_run_commands_registered_tool_adapter(
        tmp_path,
        options=RunCommandsToolOptions(
            shell_executable="/bin/sh",
            environment_builder=policies,
            permission_evaluator=policies,
            approval_resolver=policies,
            sandbox_preflight=policies,
            limits=CommandExecutionLimits(max_concurrent_commands=1),
        ),
    )
    runtime = create_tool_loop_runtime(
        model=model,
        tools=(tool,),
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=1_000),
    )

    assert tuple(definition.name for definition in runtime.available_tools) == (RUN_COMMANDS_TOOL_NAME,)
    assert model.calls == []
    assert policies == ExplicitHostPolicies()

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Run the composed command.")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert len(model.calls) == EXPECTED_TOOL_LOOP_TURN_COUNT
    assert policies.environment_calls == 1
    assert policies.permission_calls == 1
    assert policies.approval_calls == 0
    assert policies.sandbox_calls == 1
    payload_part = result.tool_results[0].content[0]
    assert isinstance(payload_part, ToolTextContent)
    payload = json.loads(payload_part.text)
    assert payload["results"][0]["stdout"] == "composed\n"
    assert payload["results"][0]["success"] is True


def test_run_commands_factory_fails_closed_without_an_injected_supervisor_on_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Require an explicit platform supervisor outside default POSIX support."""
    monkeypatch.setattr(workspace_command_execution.sys, "platform", "win32")
    policies = ExplicitHostPolicies()

    with pytest.raises(RuntimeError, match="provide a supervisor"):
        create_run_commands_registered_tool_adapter(
            tmp_path,
            options=RunCommandsToolOptions(
                shell_executable="/bin/sh",
                environment_builder=policies,
                permission_evaluator=policies,
                approval_resolver=policies,
                sandbox_preflight=policies,
            ),
        )

    assert policies == ExplicitHostPolicies()
