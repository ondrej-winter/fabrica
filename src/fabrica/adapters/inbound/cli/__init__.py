"""Command-line inbound adapter for local agent runtime workflows."""

from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.parser import (
    CliCommand,
    CliInvocation,
    build_parser,
    parse_args,
)
from fabrica.adapters.inbound.cli.runner import (
    CliCommandDependencies,
    CommandAugmenter,
    CommitMessageWorkflowRunner,
    ConfirmedCommitWorkflowRunner,
    LocalAgentRuntime,
    ScriptExecutor,
    ScriptPolicyEvaluator,
    run_cli_command,
)
from fabrica.features.agent_runtime.adapters.inbound.cli import (
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
)
from fabrica.features.developer_workflow.adapters.inbound.cli import (
    CliCommitCommand,
    CliCommitMessageCommand,
)

__all__ = [
    "CliCommand",
    "CliCommandDependencies",
    "CliCommitCommand",
    "CliCommitMessageCommand",
    "CliGlobalOptions",
    "CliInvocation",
    "CliRunCommand",
    "CliScriptExecuteCommand",
    "CliScriptPolicyCommand",
    "CliSelectedResource",
    "CommandAugmenter",
    "CommitMessageWorkflowRunner",
    "ConfirmedCommitWorkflowRunner",
    "LocalAgentRuntime",
    "ScriptExecutor",
    "ScriptPolicyEvaluator",
    "build_parser",
    "parse_args",
    "run_cli_command",
]
