"""Command-line inbound adapter for local agent runtime workflows."""

from fabrica.features.agent_runtime.adapters.inbound.cli.parser import (
    CliCommand,
    CliCommitMessageCommand,
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
    build_parser,
    parse_args,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import (
    CliCommandDependencies,
    CommandAugmenter,
    CommitMessageWorkflowRunner,
    LocalAgentRuntime,
    ScriptExecutor,
    ScriptPolicyEvaluator,
    run_cli_command,
)

__all__ = [
    "CliCommand",
    "CliCommandDependencies",
    "CliCommitMessageCommand",
    "CliRunCommand",
    "CliScriptExecuteCommand",
    "CliScriptPolicyCommand",
    "CliSelectedResource",
    "CommandAugmenter",
    "CommitMessageWorkflowRunner",
    "LocalAgentRuntime",
    "ScriptExecutor",
    "ScriptPolicyEvaluator",
    "build_parser",
    "parse_args",
    "run_cli_command",
]
