"""Pure structural validation for raw run-commands requests."""
# ruff: noqa: EM101, TRY003, TRY004, TRY300, TRY301

from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.workspace_command_execution.application.dtos import (
    CommandError,
    CommandErrorCode,
    CommandExecutionLimits,
    CommandExecutionMode,
    CommandExecutionStatus,
    CommandRequest,
    CommandResult,
    ExecutionPolicy,
    RunCommandsCommand,
)


@dataclass(frozen=True, slots=True)
class ValidatedCommandBatch:
    """Ordered normalized requests and command-scoped pre-spawn rejections."""

    execution: ExecutionPolicy
    entries: tuple[CommandRequest | CommandResult, ...]

    @property
    def command(self) -> RunCommandsCommand | None:
        """Return an executable batch only when every command is structurally valid."""
        if any(isinstance(item, CommandResult) for item in self.entries):
            return None
        return RunCommandsCommand(
            self.execution, tuple(item for item in self.entries if isinstance(item, CommandRequest))
        )


def validate_run_commands_request(raw: object, *, limits: CommandExecutionLimits) -> ValidatedCommandBatch:
    """Normalize a raw batch while isolating malformed individual commands."""
    if not isinstance(raw, Mapping):
        raise TypeError("run_commands request must be an object")
    if set(raw) - {"execution", "commands"}:
        raise ValueError("run_commands request must not include additional properties")
    try:
        execution = ExecutionPolicy(raw.get("execution", "parallel"))
    except (TypeError, ValueError) as err:
        raise ValueError("execution must be parallel or sequential") from err
    commands = raw.get("commands")
    if not isinstance(commands, list):
        raise TypeError("commands must be an array")
    if not commands or len(commands) > limits.max_commands_per_call:
        raise ValueError("commands must be non-empty and within the host batch bound")
    return ValidatedCommandBatch(execution, tuple(_command(item, index, limits) for index, item in enumerate(commands)))


def _command(raw: object, index: int, limits: CommandExecutionLimits) -> CommandRequest | CommandResult:
    try:
        if not isinstance(raw, Mapping):
            raise ValueError("command must be an object")
        if set(raw) - {"argv", "shell", "cwd", "env", "timeout_ms"}:
            raise ValueError("command must not include additional properties")
        has_argv, has_shell = "argv" in raw, "shell" in raw
        if has_argv == has_shell:
            raise ValueError("command must contain exactly one of argv or shell")
        kwargs = {
            "cwd": raw.get("cwd", "."),
            "env": raw.get("env", {}),
            "timeout_ms": raw.get("timeout_ms", limits.default_command_timeout_ms),
        }
        if has_argv:
            argv = raw["argv"]
            if not isinstance(argv, list):
                raise ValueError("argv must be an array of strings")
            request = CommandRequest(CommandExecutionMode.ARGV, argv=tuple(argv), **kwargs)
        else:
            request = CommandRequest(CommandExecutionMode.SHELL, shell=raw["shell"], **kwargs)
        if request.input_chars > limits.max_command_input_chars:
            raise ValueError("command input exceeds the host bound")
        if request.timeout_ms > limits.max_command_timeout_ms:
            raise ValueError("timeout_ms exceeds the host maximum")
        return request
    except (TypeError, ValueError) as err:
        code = (
            CommandErrorCode.COMMAND_INPUT_TOO_LARGE if "input exceeds" in str(err) else CommandErrorCode.INVALID_INPUT
        )
        if "timeout_ms exceeds" in str(err):
            code = CommandErrorCode.COMMAND_TIMEOUT_TOO_LARGE
        return CommandResult(index, "", CommandExecutionStatus.SPAWN_FAILED, 0, error=CommandError(code, str(err)))
