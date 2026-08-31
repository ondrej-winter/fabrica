"""Model-facing registered-tool adapter for workspace command execution."""

from fabrica.features.workspace_command_execution.adapters.inbound.registered_tool.adapter import (
    RUN_COMMANDS_TOOL_DEFINITION,
    RUN_COMMANDS_TOOL_DESCRIPTION,
    RUN_COMMANDS_TOOL_NAME,
    RunCommandsRegisteredToolAdapter,
    create_run_commands_registered_tool,
)

__all__ = [
    "RUN_COMMANDS_TOOL_DEFINITION",
    "RUN_COMMANDS_TOOL_DESCRIPTION",
    "RUN_COMMANDS_TOOL_NAME",
    "RunCommandsRegisteredToolAdapter",
    "create_run_commands_registered_tool",
]
