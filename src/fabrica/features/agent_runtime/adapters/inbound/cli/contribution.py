"""Agent-runtime CLI contribution metadata."""

from __future__ import annotations

from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import register_agent_runtime_cli_commands

AGENT_RUNTIME_CLI_COMMAND_TYPES: tuple[type[object], ...] = (
    CliRunCommand,
    CliScriptPolicyCommand,
    CliScriptExecuteCommand,
)

__all__ = [
    "AGENT_RUNTIME_CLI_COMMAND_TYPES",
    "register_agent_runtime_cli_commands",
]
