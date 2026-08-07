"""Argparse registration for developer-workflow CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.use_cases import DEFAULT_COMMIT_MESSAGE_SKILL_ID

if TYPE_CHECKING:
    import argparse


def register_developer_workflow_cli_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register developer-workflow owned commands on the product CLI parser."""
    commit_message_parser = subparsers.add_parser(
        "commit-message",
        help="preview a read-only commit message for staged git changes",
        description="Read staged git diff context and propose a commit message without creating a commit.",
    )
    _add_commit_message_generation_flags(commit_message_parser)
    _add_common_skill_root_flags(commit_message_parser)
    commit_message_parser.set_defaults(command_factory=_commit_message_command_from_namespace)

    commit_parser = subparsers.add_parser(
        "commit",
        help="create a git commit from a generated message after confirmation",
        description=(
            "Generate a staged-changes commit message, prompt for confirmation, "
            "then create a git commit only after approval."
        ),
    )
    _add_commit_message_generation_flags(commit_parser)
    _add_common_skill_root_flags(commit_parser)
    commit_parser.set_defaults(command_factory=_commit_command_from_namespace)


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


def _commit_message_command_from_namespace(namespace: argparse.Namespace) -> CliCommitMessageCommand:
    return CliCommitMessageCommand(
        skill_id=namespace.skill_id,
        model=namespace.model,
        reasoning_effort=namespace.reasoning_effort,
        skill_roots=tuple(namespace.skill_roots),
    )


def _commit_command_from_namespace(namespace: argparse.Namespace) -> CliCommitCommand:
    return CliCommitCommand(
        skill_id=namespace.skill_id,
        model=namespace.model,
        reasoning_effort=namespace.reasoning_effort,
        skill_roots=tuple(namespace.skill_roots),
    )
