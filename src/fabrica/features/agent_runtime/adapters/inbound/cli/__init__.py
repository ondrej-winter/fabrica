"""Agent-runtime CLI command adapters."""

from fabrica.features.agent_runtime.adapters.inbound.cli.commands import (
    AgentRuntimeCliDependencies,
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
    CommandAugmenter,
    LocalAgentRuntime,
    ScriptExecutor,
    ScriptPolicyEvaluator,
    register_agent_runtime_cli_commands,
    run_agent_runtime_cli_command,
)

__all__ = [
    "AgentRuntimeCliDependencies",
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
