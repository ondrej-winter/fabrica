"""Argparse registration for developer-workflow CLI commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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
    from collections.abc import Callable

    from fabrica.adapters.inbound.cli import CliCommandRegistry, CliExecutionContext

COMMIT_MESSAGE_COMMAND_NAME = "commit-message"
COMMIT_COMMAND_NAME = "commit"
DEVELOPER_WORKFLOW_CLI_COMMAND_NAMES = (COMMIT_MESSAGE_COMMAND_NAME, COMMIT_COMMAND_NAME)
type DeveloperWorkflowCliHandler[TCommand] = Callable[
    [TCommand, CliDeveloperWorkflowCompositionOptions, CliExecutionContext], int
]


@dataclass(frozen=True, slots=True)
class _ParsedDeveloperWorkflowCliCommand[TCommand]:
    command: TCommand
    composition_options: CliDeveloperWorkflowCompositionOptions


def register_developer_workflow_cli_commands(
    commands: CliCommandRegistry,
    *,
    commit_message_command: DeveloperWorkflowCliHandler[CliCommitMessageCommand],
    commit_command: DeveloperWorkflowCliHandler[CliCommitCommand],
) -> None:
    """Register developer-workflow owned commands on the product CLI parser."""
    commands.register_command(
        name=COMMIT_MESSAGE_COMMAND_NAME,
        summary="preview a read-only commit message for staged git changes",
        configure_parser=_configure_commit_message_parser,
        decode=_parsed_commit_message_command_from_namespace,
        handler=_handler_for_commit_message_command(commit_message_command),
        description="Read staged git diff context and propose a commit message without creating a commit.",
    )

    commands.register_command(
        name=COMMIT_COMMAND_NAME,
        summary="run pre-commit, then create a git commit from a generated message after confirmation",
        configure_parser=_configure_commit_parser,
        decode=_parsed_commit_command_from_namespace,
        handler=_handler_for_commit_command(commit_command),
        description=(
            "Run the staged pre-commit quality gate before message generation, "
            "prompt for confirmation, then create a git commit only after approval."
        ),
    )


def _configure_commit_message_parser(parser: argparse.ArgumentParser) -> None:
    _add_commit_message_generation_flags(parser)
    _add_common_skill_root_flags(parser)


def _configure_commit_parser(parser: argparse.ArgumentParser) -> None:
    _add_commit_message_generation_flags(parser)
    _add_common_skill_root_flags(parser)


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


def _parsed_commit_message_command_from_namespace(
    namespace: argparse.Namespace,
) -> _ParsedDeveloperWorkflowCliCommand[CliCommitMessageCommand]:
    return _ParsedDeveloperWorkflowCliCommand(
        command=_commit_message_command_from_namespace(namespace),
        composition_options=_developer_workflow_composition_options_from_namespace(namespace),
    )


def _parsed_commit_command_from_namespace(
    namespace: argparse.Namespace,
) -> _ParsedDeveloperWorkflowCliCommand[CliCommitCommand]:
    return _ParsedDeveloperWorkflowCliCommand(
        command=_commit_command_from_namespace(namespace),
        composition_options=_developer_workflow_composition_options_from_namespace(namespace),
    )


def _handler_for_commit_message_command(
    handler: DeveloperWorkflowCliHandler[CliCommitMessageCommand],
) -> Callable[[_ParsedDeveloperWorkflowCliCommand[CliCommitMessageCommand], CliExecutionContext], int]:
    def run(parsed: _ParsedDeveloperWorkflowCliCommand[CliCommitMessageCommand], context: CliExecutionContext) -> int:
        return handler(
            parsed.command,
            parsed.composition_options,
            context,
        )

    return run


def _handler_for_commit_command(
    handler: DeveloperWorkflowCliHandler[CliCommitCommand],
) -> Callable[[_ParsedDeveloperWorkflowCliCommand[CliCommitCommand], CliExecutionContext], int]:
    def run(parsed: _ParsedDeveloperWorkflowCliCommand[CliCommitCommand], context: CliExecutionContext) -> int:
        return handler(
            parsed.command,
            parsed.composition_options,
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
