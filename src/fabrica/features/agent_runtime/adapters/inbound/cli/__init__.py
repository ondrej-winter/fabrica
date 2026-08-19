"""Agent-runtime CLI command adapters."""

from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    AgentRuntimeCliCompositionOptions,
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliOptions,
    AgentRuntimeCliStreams,
    EvidenceWriter,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import (
    AGENT_RUNTIME_CLI_COMMAND_NAMES,
    AgentRuntimeCliHandler,
    register_agent_runtime_cli_commands,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import (
    run_local_agent_cli_command,
    run_script_execute_cli_command,
    run_script_policy_cli_command,
    run_selected_context_agent_cli_command,
)

__all__ = [
    "AGENT_RUNTIME_CLI_COMMAND_NAMES",
    "AgentRuntimeCliCompositionOptions",
    "AgentRuntimeCliHandler",
    "AgentRuntimeCliOptions",
    "AgentRuntimeCliStreams",
    "CliRunCommand",
    "CliScriptExecuteCommand",
    "CliScriptPolicyCommand",
    "CliSelectedResource",
    "EvidenceWriter",
    "register_agent_runtime_cli_commands",
    "run_local_agent_cli_command",
    "run_script_execute_cli_command",
    "run_script_policy_cli_command",
    "run_selected_context_agent_cli_command",
]
