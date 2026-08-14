"""Argparse registration for developer-workflow CLI commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contracts import bind_cli_handler
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CliDeveloperWorkflowCompositionOptions,
)
from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_COMMIT_MESSAGE_SKILL_ID,
    GenerateCommitMessageCommand,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from fabrica.adapters.inbound.cli.contracts import CliExecutionContext, CliSubparsers

COMMIT_MESSAGE_COMMAND_NAME = "commit-message"
COMMIT_COMMAND_NAME = "commit"
DEVELOPER_WORKFLOW_CLI_COMMAND_NAMES = (COMMIT_MESSAGE_COMMAND_NAME, COMMIT_COMMAND_NAME)
type DeveloperWorkflowCliHandler[TCommand] = Callable[
    [TCommand, CliDeveloperWorkflowCompositionOptions, CliExecutionContext], int
]


def register_developer_workflow_cli_commands(
    subparsers: CliSubparsers,
    *,
    commit_message_command: DeveloperWorkflowCliHandler[CliCommitMessageCommand],
    commit_command: DeveloperWorkflowCliHandler[CliCommitCommand],
) -> None:
    """Register developer-workflow owned commands on the product CLI parser."""
    commit_message_parser = subparsers.add_parser(
        COMMIT_MESSAGE_COMMAND_NAME,
        help="preview a read-only commit message for staged git changes",
        description="Read staged git diff context and propose a commit message without creating a commit.",
    )
    _add_commit_message_generation_flags(commit_message_parser)
    _add_common_skill_root_flags(commit_message_parser)
    bind_cli_handler(commit_message_parser, _handler_for_commit_message_command(commit_message_command))

    commit_parser = subparsers.add_parser(
        COMMIT_COMMAND_NAME,
        help="run pre-commit, then create a git commit from a generated message after confirmation",
        description=(
            "Run the staged pre-commit quality gate before message generation, "
            "prompt for confirmation, then create a git commit only after approval."
        ),
    )
    _add_commit_message_generation_flags(commit_parser)
    _add_common_skill_root_flags(commit_parser)
    bind_cli_handler(commit_parser, _handler_for_commit_command(commit_command))


def _add_common_skill_root_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skill-root",
        dest="skill_roots",
        action="append",
        type=Path,
        default=[],
        help="Skill root override for explicit skill/resource/script selection. May be repeated.",
    )


def _add_commit_message_generation_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skill",
        dest="skill_id",
        type=_parse_skill_id,
        default=DEFAULT_COMMIT_MESSAGE_SKILL_ID,
        help="Selected commit-message Agent Skill ID. Defaults to conventional-commits.",
    )
    parser.add_argument(
        "--model",
        dest="model",
        help="Optional Codex model override for commit-message generation.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max", "ultra"),
        help="Optional Codex reasoning effort override for commit-message generation.",
    )


def _parse_skill_id(value: str) -> str:
    try:
        return GenerateCommitMessageCommand(skill_id=value).skill_id
    except ValueError as err:
        raise argparse.ArgumentTypeError(str(err)) from err


def _commit_message_command_from_namespace(namespace: argparse.Namespace) -> CliCommitMessageCommand:
    return CliCommitMessageCommand(skill_id=namespace.skill_id)


def _commit_command_from_namespace(namespace: argparse.Namespace) -> CliCommitCommand:
    return CliCommitCommand(skill_id=namespace.skill_id)


def _handler_for_commit_message_command(
    handler: DeveloperWorkflowCliHandler[CliCommitMessageCommand],
) -> Callable[[argparse.Namespace, CliExecutionContext], int]:
    def run(namespace: argparse.Namespace, context: CliExecutionContext) -> int:
        return handler(
            _commit_message_command_from_namespace(namespace),
            _developer_workflow_composition_options_from_namespace(namespace),
            context,
        )

    return run


def _handler_for_commit_command(
    handler: DeveloperWorkflowCliHandler[CliCommitCommand],
) -> Callable[[argparse.Namespace, CliExecutionContext], int]:
    def run(namespace: argparse.Namespace, context: CliExecutionContext) -> int:
        return handler(
            _commit_command_from_namespace(namespace),
            _developer_workflow_composition_options_from_namespace(namespace),
            context,
        )

    return run


def _developer_workflow_composition_options_from_namespace(
    namespace: argparse.Namespace,
) -> CliDeveloperWorkflowCompositionOptions:
    return CliDeveloperWorkflowCompositionOptions(
        model=namespace.model,
        reasoning_effort=namespace.reasoning_effort,
        skill_roots=tuple(namespace.skill_roots),
    )
