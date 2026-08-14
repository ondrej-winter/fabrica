"""Developer-workflow CLI contribution metadata."""

from __future__ import annotations

from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.registration import (
    COMMIT_COMMAND_NAME,
    COMMIT_MESSAGE_COMMAND_NAME,
    DEVELOPER_WORKFLOW_CLI_COMMAND_NAMES,
    register_developer_workflow_cli_commands,
)

DEVELOPER_WORKFLOW_CLI_COMMAND_TYPES: tuple[type[CliCommitMessageCommand | CliCommitCommand], ...] = (
    CliCommitMessageCommand,
    CliCommitCommand,
)

__all__ = [
    "COMMIT_COMMAND_NAME",
    "COMMIT_MESSAGE_COMMAND_NAME",
    "DEVELOPER_WORKFLOW_CLI_COMMAND_NAMES",
    "DEVELOPER_WORKFLOW_CLI_COMMAND_TYPES",
    "register_developer_workflow_cli_commands",
]
