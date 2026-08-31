"""Expose bounded workspace command execution as one model-facing registered tool."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from fabrica.features.agent_runtime.application.dtos import (
    MAX_TOOL_CONTENT_TEXT_CHARS,
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolDefinition,
    ToolExecutionContext,
    ToolMutationGuarantee,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_command_execution.application.dtos import (
    DEFAULT_MAX_COMMANDS_PER_CALL,
    CommandExecutionLimits,
    CommandExecutionMode,
    CommandRequest,
    ExecutionPolicy,
    RunCommandsCommand,
    RunCommandsResult,
)
from fabrica.features.workspace_command_execution.application.ports import RunCommandsContext, RunCommandsPort
from fabrica.features.workspace_command_execution.application.result_formatting import serialize_run_commands_result

RUN_COMMANDS_TOOL_NAME = "run_commands"
RUN_COMMANDS_TOOL_DESCRIPTION = """Run non-interactive commands in the workspace.

Prefer direct argv execution for ordinary commands. Use shell only when shell
syntax such as pipelines, redirects, or expansion is genuinely required.

Commands run in parallel by default. Set execution to sequential when later
commands must start only after earlier commands finish. Sequential execution
does not stop after an ordinary command failure.

Each result preserves separate stdout and stderr and is bounded. Prefer
read_files or search_codebase when you only need workspace contents."""
RUN_COMMANDS_TOOL_DEFINITION = ToolDefinition(
    name=RUN_COMMANDS_TOOL_NAME,
    description=RUN_COMMANDS_TOOL_DESCRIPTION,
    argument_schema={
        "type": "object",
        "properties": {
            "execution": {"type": "string", "enum": ("parallel", "sequential"), "default": "parallel"},
            "commands": {
                "type": "array",
                "minItems": 1,
                "maxItems": DEFAULT_MAX_COMMANDS_PER_CALL,
                "items": {
                    "type": "object",
                    "oneOf": (
                        {"required": ("argv",), "not": {"required": ("shell",)}},
                        {"required": ("shell",), "not": {"required": ("argv",)}},
                    ),
                    "properties": {
                        "argv": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 256,
                            "items": {"type": "string", "maxLength": 12_000},
                        },
                        "shell": {"type": "string", "minLength": 1, "maxLength": 12_000},
                        "cwd": {"type": "string", "minLength": 1},
                        "env": {"type": "object", "additionalProperties": {"type": "string"}},
                        "timeout_ms": {"type": "integer", "minimum": 1, "maximum": 300_000},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "required": ("commands",),
        "additionalProperties": False,
    },
)


@dataclass(frozen=True, slots=True)
class RunCommandsRegisteredToolAdapter:
    """Map canonical model arguments to the workspace-command execution port."""

    use_case: RunCommandsPort
    limits: CommandExecutionLimits

    async def handle(
        self,
        arguments: Mapping[str, ToolArgumentValue],
        context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        """Validate a batch request and return its bounded structured result."""
        try:
            command = _command_from_arguments(arguments)
        except (TypeError, ValueError) as err:
            return RegisteredToolOutcome.recoverable_rejection(
                error_code="INVALID_ARGUMENTS",
                error_message=str(err),
            )
        result = await self.use_case.run(
            command,
            RunCommandsContext(
                cancellation=context.cancellation,
                deadline_at=context.phase_deadline(RUN_COMMANDS_TOOL_NAME),
                limits=self.limits,
            ),
        )
        return run_commands_result_to_tool_outcome(result)


def create_run_commands_registered_tool(
    use_case: RunCommandsPort,
    *,
    limits: CommandExecutionLimits | None = None,
) -> AsyncRegisteredTool:
    """Create the sole model-facing registered tool for workspace commands."""
    adapter = RunCommandsRegisteredToolAdapter(use_case=use_case, limits=limits or CommandExecutionLimits())
    return AsyncRegisteredTool(definition=RUN_COMMANDS_TOOL_DEFINITION, handler=adapter.handle)


def run_commands_result_to_tool_outcome(result: RunCommandsResult) -> RegisteredToolOutcome:
    """Translate an application batch result to bounded multipart text content."""
    serialized = serialize_run_commands_result(result)
    return RegisteredToolOutcome.model_continue_success(
        mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
        content=tuple(
            ToolTextContent(text=serialized[index : index + MAX_TOOL_CONTENT_TEXT_CHARS])
            for index in range(0, len(serialized), MAX_TOOL_CONTENT_TEXT_CHARS)
        ),
    )


def _command_from_arguments(arguments: Mapping[str, ToolArgumentValue]) -> RunCommandsCommand:
    if set(arguments) - {"execution", "commands"} or "commands" not in arguments:
        msg = "run_commands requires commands and accepts only optional execution"
        raise ValueError(msg)
    execution = _execution_policy(arguments.get("execution", "parallel"))
    raw_commands = arguments["commands"]
    if not isinstance(raw_commands, tuple) or not raw_commands:
        msg = "run_commands requires a non-empty commands array"
        raise ValueError(msg)
    if len(raw_commands) > DEFAULT_MAX_COMMANDS_PER_CALL:
        msg = f"run_commands accepts at most {DEFAULT_MAX_COMMANDS_PER_CALL} commands"
        raise ValueError(msg)
    return RunCommandsCommand(execution=execution, commands=tuple(_command_request(value) for value in raw_commands))


def _execution_policy(value: ToolArgumentValue) -> ExecutionPolicy:
    if not isinstance(value, str):
        msg = "execution must be parallel or sequential"
        raise TypeError(msg)
    try:
        return ExecutionPolicy(value)
    except ValueError as err:
        msg = "execution must be parallel or sequential"
        raise ValueError(msg) from err


def _command_request(value: ToolArgumentValue) -> CommandRequest:
    if not isinstance(value, Mapping) or not value:
        msg = "each commands entry must be an object"
        raise ValueError(msg)
    if set(value) - {"argv", "shell", "cwd", "env", "timeout_ms"}:
        msg = "commands entries must not include additional properties"
        raise ValueError(msg)
    argv = value.get("argv")
    shell = value.get("shell")
    if (argv is None) == (shell is None):
        msg = "each commands entry requires exactly one of argv or shell"
        raise ValueError(msg)
    cwd = value.get("cwd", ".")
    if not isinstance(cwd, str):
        msg = "command cwd must be a string"
        raise TypeError(msg)
    environment = _environment(value.get("env", {}))
    timeout_ms = value.get("timeout_ms", 30_000)
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
        msg = "command timeout_ms must be an integer"
        raise TypeError(msg)
    if shell is not None:
        if not isinstance(shell, str):
            msg = "command shell must be a string"
            raise TypeError(msg)
        return CommandRequest(
            mode=CommandExecutionMode.SHELL,
            shell=shell,
            cwd=cwd,
            env=environment,
            timeout_ms=timeout_ms,
        )
    if not isinstance(argv, tuple) or not all(isinstance(item, str) for item in argv):
        msg = "command argv must be an array of strings"
        raise TypeError(msg)
    return CommandRequest(
        mode=CommandExecutionMode.ARGV,
        argv=cast("tuple[str, ...]", argv),
        cwd=cwd,
        env=environment,
        timeout_ms=timeout_ms,
    )


def _environment(value: ToolArgumentValue) -> dict[str, str]:
    valid_mapping = isinstance(value, Mapping) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )
    if not valid_mapping:
        msg = "command env must be an object with string keys and values"
        raise TypeError(msg)
    return {cast("str", key): cast("str", item) for key, item in value.items()}


__all__ = [
    "RUN_COMMANDS_TOOL_DEFINITION",
    "RUN_COMMANDS_TOOL_DESCRIPTION",
    "RUN_COMMANDS_TOOL_NAME",
    "RunCommandsRegisteredToolAdapter",
    "create_run_commands_registered_tool",
    "run_commands_result_to_tool_outcome",
]
