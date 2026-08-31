"""Tests for the model-facing run-commands registered-tool adapter."""

import asyncio
import json
from asyncio import run
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
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
from fabrica.features.workspace_command_execution.adapters.inbound.registered_tool import (
    RUN_COMMANDS_TOOL_DEFINITION,
    RUN_COMMANDS_TOOL_DESCRIPTION,
    RUN_COMMANDS_TOOL_NAME,
    RunCommandsRegisteredToolAdapter,
    create_run_commands_registered_tool,
)
from fabrica.features.workspace_command_execution.adapters.inbound.registered_tool.adapter import (
    run_commands_result_to_tool_outcome,
)
from fabrica.features.workspace_command_execution.application.dtos import (
    CommandExecutionLimits,
    CommandExecutionMode,
    CommandExecutionOutput,
    CommandExecutionStatus,
    CommandRequest,
    CommandResult,
    ExecutionPolicy,
    RunCommandsCommand,
    RunCommandsResult,
)
from fabrica.features.workspace_command_execution.application.ports import RunCommandsContext

PHASE_DEADLINE = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MULTIPART_TEXT_PART_COUNT = 2


def test_run_commands_registered_tool_exposes_the_closed_canonical_schema_and_description() -> None:
    tool = create_run_commands_registered_tool(_FakeRunCommands(_result()))

    assert tool.definition == RUN_COMMANDS_TOOL_DEFINITION
    assert tool.definition.name == RUN_COMMANDS_TOOL_NAME
    schema = cast("dict[str, ToolArgumentSchemaValue]", tool.definition.argument_schema)
    properties = cast("dict[str, ToolArgumentSchemaValue]", schema["properties"])
    commands = cast("dict[str, ToolArgumentSchemaValue]", properties["commands"])
    items = cast("dict[str, ToolArgumentSchemaValue]", commands["items"])
    assert schema["required"] == ("commands",)
    assert schema["additionalProperties"] is False
    assert commands["minItems"] == 1
    assert commands["maxItems"] == CommandExecutionLimits().max_commands_per_call
    assert len(cast("tuple[object, ...]", items["oneOf"])) == MULTIPART_TEXT_PART_COUNT
    assert items["additionalProperties"] is False
    assert RUN_COMMANDS_TOOL_DESCRIPTION.startswith("Run non-interactive commands in the workspace.")
    assert "Prefer direct argv execution" in RUN_COMMANDS_TOOL_DESCRIPTION


def test_run_commands_registered_tool_maps_arguments_and_runtime_context_to_the_use_case() -> None:
    use_case = _FakeRunCommands(_result())
    limits = CommandExecutionLimits(max_concurrent_commands=1)
    adapter = RunCommandsRegisteredToolAdapter(use_case=use_case, limits=limits)
    arguments = {
        "execution": "sequential",
        "commands": (
            {"argv": ("uv", "run", "pytest"), "cwd": "tests", "env": {"CI": "1"}, "timeout_ms": 5_000},
            {"shell": "git status --short"},
        ),
    }

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command == RunCommandsCommand(
        execution=ExecutionPolicy.SEQUENTIAL,
        commands=(
            CommandRequest(
                mode=CommandExecutionMode.ARGV,
                argv=("uv", "run", "pytest"),
                cwd="tests",
                env={"CI": "1"},
                timeout_ms=5_000,
            ),
            CommandRequest(mode=CommandExecutionMode.SHELL, shell="git status --short"),  # noqa: S604
        ),
    )
    assert use_case.context == RunCommandsContext(
        cancellation=_NeverCancelled(),
        deadline_at=PHASE_DEADLINE,
        limits=limits,
    )
    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert outcome.mutation_guarantee is ToolMutationGuarantee.NO_MUTATION
    payload = json.loads(_serialized_content(outcome))
    assert payload["execution"] == "parallel"


def test_run_commands_registered_tool_defaults_execution_and_command_options() -> None:
    use_case = _FakeRunCommands(_result())
    adapter = RunCommandsRegisteredToolAdapter(use_case=use_case, limits=CommandExecutionLimits())
    arguments = {"commands": ({"argv": ("echo", "ok")},)}

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command == RunCommandsCommand(
        execution=ExecutionPolicy.PARALLEL,
        commands=(
            CommandRequest(
                mode=CommandExecutionMode.ARGV,
                argv=("echo", "ok"),
            ),
        ),
    )
    assert outcome.status is ToolOutcomeStatus.SUCCESS


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"commands": ()},
        {"commands": ({"argv": ("echo",), "shell": "echo"},)},
        {"commands": ({"cwd": "."},)},
        {"commands": (42,)},
        {"commands": ({"argv": "echo"},)},
        {"commands": ({"shell": 42},)},
        {"commands": ({"argv": ("echo",), "cwd": 42},)},
        {"commands": ({"argv": ("echo",), "env": {"CI": 1}},)},
        {"commands": ({"argv": ("echo",), "timeout_ms": "fast"},)},
        {"commands": ({"argv": ("echo",), "unknown": True},)},
        {"execution": 42, "commands": ({"argv": ("echo",)},)},
        {"execution": "background", "commands": ({"argv": ("echo",)},)},
        {"commands": tuple({"argv": ("echo",)} for _ in range(CommandExecutionLimits().max_commands_per_call + 1))},
    ],
)
def test_run_commands_registered_tool_rejects_invalid_shapes_without_executing_the_use_case(
    arguments: Mapping[str, ToolArgumentValue],
) -> None:
    use_case = _FakeRunCommands(_result())
    adapter = RunCommandsRegisteredToolAdapter(use_case=use_case, limits=CommandExecutionLimits())

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert use_case.command is None
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_ARGUMENTS"


def test_run_commands_registered_tool_preserves_ordinary_command_failures_in_a_successful_structured_result() -> None:
    result = RunCommandsResult(
        execution=ExecutionPolicy.PARALLEL,
        results=(
            CommandResult(
                index=0,
                command_preview="false",
                status=CommandExecutionStatus.EXITED,
                duration_ms=12,
                exit_code=1,
                output=CommandExecutionOutput(stderr="failed", total_output_chars=6, retained_output_chars=6),
            ),
        ),
    )
    adapter = RunCommandsRegisteredToolAdapter(_FakeRunCommands(result), CommandExecutionLimits())
    arguments = {"commands": ({"argv": ("false",)},)}

    outcome = run(adapter.handle(arguments, _context(arguments)))

    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert outcome.error_code is None
    payload = json.loads(_serialized_content(outcome))
    assert payload["results"][0]["success"] is False
    assert payload["results"][0]["stderr"] == "failed"


def test_run_commands_result_to_tool_outcome_preserves_the_complete_bounded_json_in_text_parts() -> None:
    stdout = "x" * 95_500
    result = RunCommandsResult(
        execution=ExecutionPolicy.PARALLEL,
        results=(
            CommandResult(
                index=0,
                command_preview="echo",
                status=CommandExecutionStatus.EXITED,
                duration_ms=0,
                exit_code=0,
                output=CommandExecutionOutput(
                    stdout=stdout,
                    total_output_chars=len(stdout),
                    retained_output_chars=len(stdout),
                ),
            ),
        ),
    )

    outcome = run_commands_result_to_tool_outcome(result)

    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert len(outcome.content) == MULTIPART_TEXT_PART_COUNT
    assert all(
        isinstance(part, ToolTextContent) and len(part.text) <= MAX_TOOL_CONTENT_TEXT_CHARS for part in outcome.content
    )
    assert json.loads(_serialized_content(outcome))["results"][0]["stdout"] == stdout


@dataclass(slots=True)
class _FakeRunCommands:
    result: RunCommandsResult
    command: RunCommandsCommand | None = None
    context: RunCommandsContext | None = None

    async def run(self, command: RunCommandsCommand, context: RunCommandsContext) -> RunCommandsResult:
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
        phase_deadlines=(ToolExecutionPhaseDeadline(phase=RUN_COMMANDS_TOOL_NAME, deadline_at=PHASE_DEADLINE),),
    )


def _result() -> RunCommandsResult:
    return RunCommandsResult(
        execution=ExecutionPolicy.PARALLEL,
        results=(
            CommandResult(
                index=0,
                command_preview="echo",
                status=CommandExecutionStatus.EXITED,
                duration_ms=0,
                exit_code=0,
            ),
        ),
    )


def _serialized_content(outcome: RegisteredToolOutcome) -> str:
    return "".join(part.text for part in outcome.content if isinstance(part, ToolTextContent))
