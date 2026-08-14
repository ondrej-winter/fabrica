"""Argparse registration for developer-workflow CLI commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

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
    from fabrica.adapters.inbound.cli.contracts import CliSubparsers

COMMIT_MESSAGE_COMMAND_NAME = "commit-message"
COMMIT_COMMAND_NAME = "commit"
DEVELOPER_WORKFLOW_CLI_COMMAND_NAMES = (COMMIT_MESSAGE_COMMAND_NAME, COMMIT_COMMAND_NAME)


def register_developer_workflow_cli_commands(subparsers: CliSubparsers) -> None:
    """Register developer-workflow owned commands on the product CLI parser."""
    commit_message_parser = subparsers.add_parser(
        COMMIT_MESSAGE_COMMAND_NAME,
        help="preview a read-only commit message for staged git changes",
        description="Read staged git diff context and propose a commit message without creating a commit.",
    )
    _add_commit_message_generation_flags(commit_message_parser)
    _add_common_skill_root_flags(commit_message_parser)
    commit_message_parser.set_defaults(command_factory=_commit_message_command_from_namespace)
    commit_message_parser.set_defaults(
        composition_options_factory=_developer_workflow_composition_options_from_namespace
    )

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
    commit_parser.set_defaults(command_factory=_commit_command_from_namespace)
    commit_parser.set_defaults(composition_options_factory=_developer_workflow_composition_options_from_namespace)


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


def _developer_workflow_composition_options_from_namespace(
    namespace: argparse.Namespace,
) -> CliDeveloperWorkflowCompositionOptions:
    return CliDeveloperWorkflowCompositionOptions(
        model=namespace.model,
        reasoning_effort=namespace.reasoning_effort,
        skill_roots=tuple(namespace.skill_roots),
    )
