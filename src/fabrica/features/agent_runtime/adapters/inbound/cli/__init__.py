"""Agent-runtime CLI command adapters."""

from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliDependencies,
    AgentRuntimeCliStreams,
    CommandAugmenter,
    LocalAgentRuntime,
    ScriptExecutor,
    ScriptPolicyEvaluator,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import (
    register_agent_runtime_cli_commands,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import (
    run_agent_runtime_cli_command,
)

__all__ = [
    "AgentRuntimeCliDependencies",
    "AgentRuntimeCliStreams",
    "CliRunCommand",
    "CliScriptExecuteCommand",
    "CliScriptPolicyCommand",
    "CliSelectedResource",
    "CommandAugmenter",
    "LocalAgentRuntime",
    "ScriptExecutor",
    "ScriptPolicyEvaluator",
    "register_agent_runtime_cli_commands",
    "run_agent_runtime_cli_command",
]
