"""Tests for run-commands application DTO invariants."""

from typing import cast

import pytest

from fabrica.features.workspace_command_execution.application.dtos import (
    CommandError,
    CommandErrorCode,
    CommandExecutionLimits,
    CommandExecutionMode,
    CommandExecutionOutput,
    CommandExecutionStatus,
    CommandRequest,
    CommandResult,
    ExecutionPolicy,
    PlannedCommand,
    RunCommandsCommand,
    RunCommandsResult,
    SkippedCommandReason,
)


def test_command_request_supports_argv_and_shell_with_immutable_environment() -> None:
    argv_request = CommandRequest(CommandExecutionMode.ARGV, argv=("git", "status"), env={"CI": "1"})
    shell_request = CommandRequest(CommandExecutionMode.SHELL, shell="echo ok")  # noqa: S604 - DTO keyword, no execution.

    assert argv_request.input_chars == len("git status")
    assert dict(argv_request.env) == {"CI": "1"}
    assert shell_request.input_chars == len("echo ok")


@pytest.mark.parametrize(
    ("mode", "argv", "shell"),
    [
        (CommandExecutionMode.ARGV, None, None),
        (CommandExecutionMode.ARGV, ("ok",), "echo ok"),
        (CommandExecutionMode.SHELL, ("ok",), "echo ok"),
        (CommandExecutionMode.SHELL, None, ""),
    ],
)
def test_command_request_rejects_nonexclusive_or_empty_execution_forms(
    mode: CommandExecutionMode,
    argv: tuple[str, ...] | None,
    shell: str | None,
) -> None:
    with pytest.raises(ValueError, match=r"require|must"):
        CommandRequest(mode, argv=argv, shell=shell)


@pytest.mark.parametrize("cwd", ["/workspace", "../outside", "dir\\child", "", "dir/../child"])
def test_command_request_rejects_escaping_cwd_syntax(cwd: str) -> None:
    with pytest.raises(ValueError, match="workspace-relative"):
        CommandRequest(CommandExecutionMode.ARGV, argv=("git",), cwd=cwd)


def test_limits_validate_deadlines_and_concurrency() -> None:
    command_count = 2
    assert (
        CommandExecutionLimits(
            max_commands_per_call=command_count,
            max_concurrent_commands=command_count,
        ).max_commands_per_call
        == command_count
    )

    with pytest.raises(ValueError, match="max_concurrent_commands"):
        CommandExecutionLimits(max_commands_per_call=1, max_concurrent_commands=2)
    with pytest.raises(ValueError, match="default_command_timeout_ms"):
        CommandExecutionLimits(default_command_timeout_ms=2, max_command_timeout_ms=1)
    with pytest.raises(ValueError, match="batch_timeout_ms"):
        CommandExecutionLimits(batch_timeout_ms=0)


def test_results_derive_success_and_enforce_status_specific_fields() -> None:
    succeeded = CommandResult(0, "git status", CommandExecutionStatus.EXITED, 1, exit_code=0)
    failed = CommandResult(1, "git status", CommandExecutionStatus.EXITED, 1, exit_code=1)
    skipped = CommandResult(
        2,
        "git status",
        CommandExecutionStatus.SKIPPED,
        0,
        reason=SkippedCommandReason.BATCH_CANCELLED,
    )

    assert succeeded.success is True
    assert failed.success is False
    assert skipped.success is False
    with pytest.raises(ValueError, match="require exit_code"):
        CommandResult(0, "git status", CommandExecutionStatus.EXITED, 1)
    with pytest.raises(ValueError, match="only skipped"):
        CommandResult(0, "git status", CommandExecutionStatus.CANCELLED, 1, reason=SkippedCommandReason.BATCH_CANCELLED)
    with pytest.raises(ValueError, match="only exited"):
        CommandResult(0, "git status", CommandExecutionStatus.CANCELLED, 1, exit_code=1)
    signalled = CommandResult(0, "git status", CommandExecutionStatus.EXITED, 1, signal="SIGTERM")
    assert signalled.success is False


def test_output_counts_and_aggregate_result_order_are_verified() -> None:
    output = CommandExecutionOutput(stdout="out", stderr="err", total_output_chars=6, retained_output_chars=6)
    result = CommandResult(0, "echo", CommandExecutionStatus.SPAWN_FAILED, 0, output=output)

    assert RunCommandsResult(ExecutionPolicy.PARALLEL, (result,)).results == (result,)
    with pytest.raises(ValueError, match="output character counts"):
        CommandExecutionOutput(stdout="out", retained_output_chars=0)
    with pytest.raises(ValueError, match="ordered"):
        RunCommandsResult(ExecutionPolicy.PARALLEL, (CommandResult(1, "echo", CommandExecutionStatus.SPAWN_FAILED, 0),))


def test_planned_command_freezes_environment_and_errors_retain_stable_codes() -> None:
    request = CommandRequest(CommandExecutionMode.ARGV, argv=("git",))
    planned = PlannedCommand(0, request, ".", {"PATH": "/bin"})

    assert dict(planned.environment) == {"PATH": "/bin"}
    assert CommandError(CommandErrorCode.PERMISSION_DENIED, "denied").code is CommandErrorCode.PERMISSION_DENIED
    assert RunCommandsCommand(ExecutionPolicy.SEQUENTIAL, (request,)).execution is ExecutionPolicy.SEQUENTIAL


@pytest.mark.parametrize(
    ("argv", "cwd", "env", "timeout_ms"),
    [
        ((), ".", {}, 1),
        (("",), ".", {}, 1),
        (("ok", "bad\x00"), ".", {}, 1),
        (("ok",), ".", {"BAD=KEY": "value"}, 1),
        (("ok",), ".", {"KEY": "bad\x00"}, 1),
        (("ok",), ".", {}, 0),
    ],
)
def test_argv_request_rejects_invalid_arguments_environment_and_timeout(
    argv: tuple[str, ...],
    cwd: str,
    env: dict[str, str],
    timeout_ms: int,
) -> None:
    with pytest.raises(ValueError, match=r"argv|environment|timeout"):
        CommandRequest(CommandExecutionMode.ARGV, argv=argv, cwd=cwd, env=env, timeout_ms=timeout_ms)


def test_dtos_reject_unknown_mode_empty_batch_and_invalid_indexes() -> None:
    with pytest.raises(ValueError, match="mode"):
        CommandRequest(cast("CommandExecutionMode", "invalid"), argv=("ok",))
    with pytest.raises(ValueError, match="commands"):
        RunCommandsCommand(ExecutionPolicy.PARALLEL, ())
    request = CommandRequest(CommandExecutionMode.ARGV, argv=("ok",))
    with pytest.raises(ValueError, match="index"):
        PlannedCommand(-1, request, ".", {})
    with pytest.raises(ValueError, match="command_preview"):
        CommandResult(0, "x" * 201, CommandExecutionStatus.SPAWN_FAILED, 0)
