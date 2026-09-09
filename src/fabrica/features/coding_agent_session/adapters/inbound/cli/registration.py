"""Argparse registration for the coding-agent-session CLI command."""

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fabrica.adapters.inbound.cli.command import Command, CommandContext, CommandRegistry, UsageError
from fabrica.features.agent_runtime.application.dtos import SelectedSkill, SelectedSkillResource
from fabrica.features.coding_agent_session.adapters.inbound.cli.command_models import (
    CliCodingAgentSessionCommand,
    CliSelectedResource,
    CodingAgentSessionCliCompositionOptions,
)

CODING_AGENT_SESSION_COMMAND_NAME = "agent"
CODING_AGENT_SESSION_CLI_COMMAND_NAMES = (CODING_AGENT_SESSION_COMMAND_NAME,)
type CodingAgentSessionCliHandler = Callable[
    [CliCodingAgentSessionCommand, CodingAgentSessionCliCompositionOptions, CommandContext], int
]


@dataclass(frozen=True, slots=True)
class _ParsedCodingAgentSessionCommand:
    command: CliCodingAgentSessionCommand
    composition_options: CodingAgentSessionCliCompositionOptions


def register_coding_agent_session_cli_commands(
    commands: CommandRegistry,
    *,
    agent_command: CodingAgentSessionCliHandler,
) -> None:
    """Register the workspace-scoped interactive coding-agent command."""
    commands.register(
        Command(
            name=CODING_AGENT_SESSION_COMMAND_NAME,
            summary="run an interactive workspace-scoped coding agent",
            configure=_configure_agent_parser,
            decode=_command_from_namespace,
            run=_handler(agent_command),
            description="Run a tool-aware coding-agent session inside one explicitly selected workspace.",
        ),
    )


def _configure_agent_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        dest="workspace_root",
        required=True,
        type=_parse_workspace,
        help="Existing workspace directory.",
    )
    parser.add_argument("--prompt", required=True, type=_parse_prompt, help="Task for the coding-agent session.")
    parser.add_argument(
        "--skill",
        dest="skill_ids",
        action="append",
        default=[],
        type=_parse_skill_id,
        help="Explicit selected Agent Skill ID. May be repeated.",
    )
    parser.add_argument(
        "--resource",
        dest="resources",
        action="append",
        default=[],
        type=_parse_resource_selection,
        metavar="SKILL_ID:RESOURCE_ID",
        help="Explicit selected Agent Skill resource. May be repeated.",
    )
    parser.add_argument(
        "--skill-root",
        dest="skill_roots",
        action="append",
        default=[],
        type=Path,
        help="Skill root override for explicit skill/resource selection. May be repeated.",
    )


def _parse_workspace(value: str) -> Path:
    try:
        workspace_root = Path(value).expanduser().resolve(strict=True)
    except OSError as err:
        msg = "workspace cannot be resolved"
        raise argparse.ArgumentTypeError(msg) from err
    if not workspace_root.is_dir():
        msg = "workspace must be an existing directory"
        raise argparse.ArgumentTypeError(msg)
    return workspace_root


def _parse_prompt(value: str) -> str:
    if not value.strip():
        msg = "prompt must not be empty"
        raise argparse.ArgumentTypeError(msg)
    return value


def _parse_skill_id(value: str) -> str:
    try:
        return SelectedSkill(skill_id=value).skill_id
    except ValueError as err:
        raise argparse.ArgumentTypeError(str(err)) from err


def _parse_resource_selection(value: str) -> CliSelectedResource:
    skill_id, separator, resource_id = value.partition(":")
    if not separator or not skill_id or not resource_id:
        msg = "resource must use SKILL_ID:RESOURCE_ID"
        raise argparse.ArgumentTypeError(msg)
    try:
        selection = SelectedSkillResource(skill_id=skill_id, resource_id=resource_id)
    except ValueError as err:
        raise argparse.ArgumentTypeError(str(err)) from err
    return CliSelectedResource(skill_id=selection.skill_id, resource_id=selection.resource_id)


def _command_from_namespace(namespace: argparse.Namespace) -> _ParsedCodingAgentSessionCommand:
    try:
        command = CliCodingAgentSessionCommand(
            workspace_root=namespace.workspace_root,
            prompt=namespace.prompt,
            skill_ids=tuple(namespace.skill_ids),
            resources=tuple(namespace.resources),
        )
    except ValueError as err:
        raise UsageError(str(err)) from err
    return _ParsedCodingAgentSessionCommand(
        command=command,
        composition_options=CodingAgentSessionCliCompositionOptions(skill_roots=tuple(namespace.skill_roots)),
    )


def _handler(
    handler: CodingAgentSessionCliHandler,
) -> Callable[[_ParsedCodingAgentSessionCommand, CommandContext], int]:
    def run(parsed: _ParsedCodingAgentSessionCommand, context: CommandContext) -> int:
        return handler(parsed.command, parsed.composition_options, context)

    return run
