"""Agent-runtime CLI contribution metadata."""

from __future__ import annotations

from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import (
    AGENT_RUNTIME_CLI_COMMAND_NAMES,
    register_agent_runtime_cli_commands,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import (
    RUN_COMMAND_NAME as AGENT_RUNTIME_RUN_COMMAND_NAME,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import (
    SCRIPT_EXECUTE_COMMAND_NAME as AGENT_RUNTIME_SCRIPT_EXECUTE_COMMAND_NAME,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import (
    SCRIPT_POLICY_COMMAND_NAME as AGENT_RUNTIME_SCRIPT_POLICY_COMMAND_NAME,
)

AGENT_RUNTIME_CLI_COMMAND_TYPES: tuple[type[object], ...] = (
    CliRunCommand,
    CliScriptPolicyCommand,
    CliScriptExecuteCommand,
)

__all__ = [
    "AGENT_RUNTIME_CLI_COMMAND_NAMES",
    "AGENT_RUNTIME_CLI_COMMAND_TYPES",
    "AGENT_RUNTIME_RUN_COMMAND_NAME",
    "AGENT_RUNTIME_SCRIPT_EXECUTE_COMMAND_NAME",
    "AGENT_RUNTIME_SCRIPT_POLICY_COMMAND_NAME",
    "register_agent_runtime_cli_commands",
]
