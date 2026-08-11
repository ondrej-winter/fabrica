"""Developer-workflow CLI command adapters."""

from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliCommandOptions,
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliStreams,
    DeveloperWorkflowCliWriters,
    EvidenceWriter,
    RuntimeResultWriter,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contribution import DEVELOPER_WORKFLOW_CLI_COMMAND_TYPES
from fabrica.features.developer_workflow.adapters.inbound.cli.registration import (
    register_developer_workflow_cli_commands,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import (
    run_developer_workflow_cli_command,
)

__all__ = [
    "DEVELOPER_WORKFLOW_CLI_COMMAND_TYPES",
    "CliCommitCommand",
    "CliCommitMessageCommand",
    "DeveloperWorkflowCliCommandOptions",
    "DeveloperWorkflowCliDependencies",
    "DeveloperWorkflowCliStreams",
    "DeveloperWorkflowCliWriters",
    "EvidenceWriter",
    "RuntimeResultWriter",
    "register_developer_workflow_cli_commands",
    "run_developer_workflow_cli_command",
]
