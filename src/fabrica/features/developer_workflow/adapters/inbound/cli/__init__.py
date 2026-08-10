"""Developer-workflow CLI command adapters."""

from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    CommitMessageWorkflowRunner,
    ConfirmedCommitWorkflowRunner,
    DeveloperWorkflowCliCommandOptions,
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliStreams,
    DeveloperWorkflowCliWriters,
    EvidenceWriter,
    RuntimeResultWriter,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.registration import (
    register_developer_workflow_cli_commands,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import (
    run_developer_workflow_cli_command,
)

__all__ = [
    "CliCommitCommand",
    "CliCommitMessageCommand",
    "CommitMessageWorkflowRunner",
    "ConfirmedCommitWorkflowRunner",
    "DeveloperWorkflowCliCommandOptions",
    "DeveloperWorkflowCliDependencies",
    "DeveloperWorkflowCliStreams",
    "DeveloperWorkflowCliWriters",
    "EvidenceWriter",
    "RuntimeResultWriter",
    "register_developer_workflow_cli_commands",
    "run_developer_workflow_cli_command",
]
