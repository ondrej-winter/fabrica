"""Developer-workflow CLI command adapters."""

from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CliDeveloperWorkflowCompositionOptions,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliOptions,
    DeveloperWorkflowCliStreams,
    EvidenceWriter,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.registration import (
    DEVELOPER_WORKFLOW_CLI_COMMAND_NAMES,
    DeveloperWorkflowCliHandler,
    register_developer_workflow_cli_commands,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import (
    run_commit_message_cli_command,
    run_confirmed_commit_cli_command,
)

__all__ = [
    "DEVELOPER_WORKFLOW_CLI_COMMAND_NAMES",
    "CliCommitCommand",
    "CliCommitMessageCommand",
    "CliDeveloperWorkflowCompositionOptions",
    "DeveloperWorkflowCliHandler",
    "DeveloperWorkflowCliOptions",
    "DeveloperWorkflowCliStreams",
    "EvidenceWriter",
    "register_developer_workflow_cli_commands",
    "run_commit_message_cli_command",
    "run_confirmed_commit_cli_command",
]
