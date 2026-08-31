"""Immutable DTOs for the run-commands application boundary."""
# ruff: noqa: D101, D102, EM101, EM102, S101, TRY003

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

DEFAULT_MAX_COMMANDS_PER_CALL = 8
DEFAULT_MAX_COMMAND_INPUT_CHARS = 12_000
DEFAULT_COMMAND_TIMEOUT_MS = 30_000
DEFAULT_MAX_COMMAND_TIMEOUT_MS = 300_000
DEFAULT_MAX_COMMAND_PREVIEW_CHARS = 200
DEFAULT_MAX_COMMAND_OUTPUT_CHARS = 48_000
DEFAULT_MAX_SERIALIZED_RESULT_CHARS = 96_000


class ExecutionPolicy(StrEnum):
    """The host-supported batch start-order policy."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"


class CommandExecutionMode(StrEnum):
    """The normalized command invocation form."""

    ARGV = "argv"
    SHELL = "shell"


class CommandExecutionStatus(StrEnum):
    """Stable terminal status for one command."""

    EXITED = "exited"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    SPAWN_FAILED = "spawn_failed"
    SKIPPED = "skipped"


class SkippedCommandReason(StrEnum):
    """Stable batch-wide reasons for commands that never started."""

    BATCH_CANCELLED = "BATCH_CANCELLED"
    BATCH_TIMED_OUT = "BATCH_TIMED_OUT"


class CommandErrorCode(StrEnum):
    """Stable Version 1 command execution error codes."""

    INVALID_INPUT = "INVALID_INPUT"
    INVALID_CWD = "INVALID_CWD"
    CWD_OUTSIDE_WORKSPACE = "CWD_OUTSIDE_WORKSPACE"
    COMMAND_INPUT_TOO_LARGE = "COMMAND_INPUT_TOO_LARGE"
    COMMAND_TIMEOUT_TOO_LARGE = "COMMAND_TIMEOUT_TOO_LARGE"
    EXECUTABLE_NOT_FOUND = "EXECUTABLE_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SANDBOX_DENIED = "SANDBOX_DENIED"
    SPAWN_FAILED = "SPAWN_FAILED"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    COMMAND_CANCELLED = "COMMAND_CANCELLED"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    BATCH_TIMEOUT = "BATCH_TIMEOUT"
    INTERNAL_EXECUTION_ERROR = "INTERNAL_EXECUTION_ERROR"


@dataclass(frozen=True, slots=True)
class CommandExecutionLimits:
    """Host-owned bounds for one run-commands invocation."""

    max_commands_per_call: int = DEFAULT_MAX_COMMANDS_PER_CALL
    max_command_input_chars: int = DEFAULT_MAX_COMMAND_INPUT_CHARS
    default_command_timeout_ms: int = DEFAULT_COMMAND_TIMEOUT_MS
    max_command_timeout_ms: int = DEFAULT_MAX_COMMAND_TIMEOUT_MS
    max_concurrent_commands: int = DEFAULT_MAX_COMMANDS_PER_CALL
    batch_timeout_ms: int | None = None
    max_command_output_chars: int = DEFAULT_MAX_COMMAND_OUTPUT_CHARS
    max_serialized_result_chars: int = DEFAULT_MAX_SERIALIZED_RESULT_CHARS

    def __post_init__(self) -> None:
        for name in (
            "max_commands_per_call",
            "max_command_input_chars",
            "default_command_timeout_ms",
            "max_command_timeout_ms",
            "max_concurrent_commands",
            "max_command_output_chars",
            "max_serialized_result_chars",
        ):
            _positive_int(getattr(self, name), name)
        if self.max_concurrent_commands > self.max_commands_per_call:
            raise ValueError("max_concurrent_commands must not exceed max_commands_per_call")
        if self.default_command_timeout_ms > self.max_command_timeout_ms:
            raise ValueError("default_command_timeout_ms must not exceed max_command_timeout_ms")
        if self.batch_timeout_ms is not None:
            _positive_int(self.batch_timeout_ms, "batch_timeout_ms")


@dataclass(frozen=True, slots=True)
class CommandRequest:
    """One normalized but not yet host-planned command request."""

    mode: CommandExecutionMode
    argv: tuple[str, ...] | None = None
    shell: str | None = None
    cwd: str = "."
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_ms: int = DEFAULT_COMMAND_TIMEOUT_MS

    def __post_init__(self) -> None:
        argv = None if self.argv is None else tuple(self.argv)
        if self.mode is CommandExecutionMode.ARGV:
            if argv is None or self.shell is not None:
                raise ValueError("argv commands require argv and must not include shell")
            _argv(argv)
        elif self.mode is CommandExecutionMode.SHELL:
            if argv is not None or self.shell is None:
                raise ValueError("shell commands require shell and must not include argv")
            _text(self.shell, "shell")
        else:
            raise ValueError("mode must be argv or shell")
        _cwd(self.cwd)
        _environment(self.env)
        _positive_int(self.timeout_ms, "timeout_ms")
        object.__setattr__(self, "argv", argv)
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))

    @property
    def input_chars(self) -> int:
        if self.mode is CommandExecutionMode.SHELL:
            assert self.shell is not None
            return len(self.shell)
        assert self.argv is not None
        return sum(map(len, self.argv)) + len(self.argv) - 1


@dataclass(frozen=True, slots=True)
class RunCommandsCommand:
    execution: ExecutionPolicy
    commands: tuple[CommandRequest, ...]

    def __post_init__(self) -> None:
        commands = tuple(self.commands)
        if not commands:
            raise ValueError("commands must not be empty")
        object.__setattr__(self, "commands", commands)


@dataclass(frozen=True, slots=True)
class PlannedCommand:
    index: int
    request: CommandRequest
    resolved_cwd: str
    environment: Mapping[str, str]

    def __post_init__(self) -> None:
        _non_negative_int(self.index, "index")
        _cwd(self.resolved_cwd)
        _environment(self.environment)
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))


@dataclass(frozen=True, slots=True)
class CommandError:
    code: CommandErrorCode
    message: str | None = None


@dataclass(frozen=True, slots=True)
class CommandExecutionOutput:
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    total_output_chars: int = 0
    retained_output_chars: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            raise TypeError("stdout and stderr must be strings")
        _non_negative_int(self.total_output_chars, "total_output_chars")
        _non_negative_int(self.retained_output_chars, "retained_output_chars")
        retained = len(self.stdout) + len(self.stderr)
        if self.retained_output_chars != retained or self.total_output_chars < retained:
            raise ValueError("output character counts must match retained output")


@dataclass(frozen=True, slots=True)
class CommandResult:
    index: int
    command_preview: str
    status: CommandExecutionStatus
    duration_ms: int
    output: CommandExecutionOutput = field(default_factory=CommandExecutionOutput)
    exit_code: int | None = None
    signal: str | None = None
    error: CommandError | None = None
    reason: SkippedCommandReason | None = None

    def __post_init__(self) -> None:
        _non_negative_int(self.index, "index")
        _non_negative_int(self.duration_ms, "duration_ms")
        if not isinstance(self.command_preview, str) or len(self.command_preview) > DEFAULT_MAX_COMMAND_PREVIEW_CHARS:
            raise ValueError("command_preview must be a bounded string")
        if self.status is CommandExecutionStatus.EXITED and self.exit_code is None and self.signal is None:
            raise ValueError("exited results require exit_code or signal")
        if self.status is not CommandExecutionStatus.EXITED and self.exit_code is not None:
            raise ValueError("only exited results may include exit_code")
        if (self.status is CommandExecutionStatus.SKIPPED) != (self.reason is not None):
            raise ValueError("only skipped results may include a reason")

    @property
    def success(self) -> bool:
        return self.status is CommandExecutionStatus.EXITED and self.exit_code == 0


@dataclass(frozen=True, slots=True)
class RunCommandsResult:
    execution: ExecutionPolicy
    results: tuple[CommandResult, ...]
    batch_output_truncated: bool = False

    def __post_init__(self) -> None:
        results = tuple(self.results)
        if not results or tuple(item.index for item in results) != tuple(range(len(results))):
            raise ValueError("results must be non-empty and ordered from zero")
        object.__setattr__(self, "results", results)


def _text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError(f"{name} must be a non-empty string without NUL bytes")


def _argv(argv: tuple[str, ...]) -> None:
    if not argv:
        raise ValueError("argv must include an executable")
    for index, value in enumerate(argv):
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError(f"argv[{index}] must be a string without NUL bytes")
    if not argv[0]:
        raise ValueError("argv executable must not be empty")


def _cwd(value: object) -> None:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or value.startswith(("/", "\\"))
        or "\\" in value
        or ".." in value.split("/")
    ):
        raise ValueError("cwd must be a non-escaping POSIX workspace-relative path")


def _environment(values: Mapping[str, str]) -> None:
    for key, value in values.items():
        if not isinstance(key, str) or not key or "\x00" in key or "=" in key:
            raise ValueError("environment keys must be non-empty strings without NUL or equals")
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError("environment values must be strings without NUL")


def _positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _non_negative_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
