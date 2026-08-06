"""Developer-workflow CLI command adapters."""

from fabrica.features.developer_workflow.adapters.inbound.cli.commands import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CommitMessageWorkflowRunner,
    ConfirmedCommitWorkflowRunner,
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliStreams,
    register_developer_workflow_cli_commands,
    run_developer_workflow_cli_command,
)

__all__ = [
    "CliCommitCommand",
    "CliCommitMessageCommand",
    "CommitMessageWorkflowRunner",
    "ConfirmedCommitWorkflowRunner",
    "DeveloperWorkflowCliDependencies",
    "DeveloperWorkflowCliStreams",
    "register_developer_workflow_cli_commands",
    "run_developer_workflow_cli_command",
]
