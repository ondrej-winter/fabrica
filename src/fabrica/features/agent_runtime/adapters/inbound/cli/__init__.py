"""Agent-runtime CLI command adapters."""

from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliCommandOptions,
    AgentRuntimeCliDependencies,
    AgentRuntimeCliStreams,
    AgentRuntimeCliWriters,
    CommandAugmenter,
    LocalAgentRuntime,
    RunResultWriter,
    ScriptExecutionResultWriter,
    ScriptExecutor,
    ScriptPolicyEvaluator,
    ScriptPolicyResultWriter,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contribution import AGENT_RUNTIME_CLI_COMMAND_TYPES
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import (
    register_agent_runtime_cli_commands,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import (
    run_agent_runtime_cli_command,
)

__all__ = [
    "AGENT_RUNTIME_CLI_COMMAND_TYPES",
    "AgentRuntimeCliCommandOptions",
    "AgentRuntimeCliDependencies",
    "AgentRuntimeCliStreams",
    "AgentRuntimeCliWriters",
    "CliRunCommand",
    "CliScriptExecuteCommand",
    "CliScriptPolicyCommand",
    "CliSelectedResource",
    "CommandAugmenter",
    "LocalAgentRuntime",
    "RunResultWriter",
    "ScriptExecutionResultWriter",
    "ScriptExecutor",
    "ScriptPolicyEvaluator",
    "ScriptPolicyResultWriter",
    "register_agent_runtime_cli_commands",
    "run_agent_runtime_cli_command",
]
