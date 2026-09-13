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
    CliSessionRecordCommand,
    CodingAgentSessionCliCompositionOptions,
)

CODING_AGENT_SESSION_COMMAND_NAME = "agent"
CODING_AGENT_SESSION_CLI_COMMAND_NAMES = (CODING_AGENT_SESSION_COMMAND_NAME,)
type CodingAgentSessionCliCommand = CliCodingAgentSessionCommand | CliSessionRecordCommand
type CodingAgentSessionCliHandler = Callable[
    [CodingAgentSessionCliCommand, CodingAgentSessionCliCompositionOptions, CommandContext], int
]


@dataclass(frozen=True, slots=True)
class _ParsedCodingAgentSessionCommand:
    command: CodingAgentSessionCliCommand
    composition_options: CodingAgentSessionCliCompositionOptions


def register_coding_agent_session_cli_commands(
    commands: CommandRegistry,
    *,
    agent_command: CodingAgentSessionCliHandler,
) -> None:
    """Register nested start and durable-session workflows under ``agent``."""
    commands.register(
        Command(
            name=CODING_AGENT_SESSION_COMMAND_NAME,
            summary="start and manage workspace-scoped coding-agent sessions",
            configure=_configure_agent_parser,
            decode=_command_from_namespace,
            run=_handler(agent_command),
            description="Start or manage durable tool-aware coding-agent sessions in one selected workspace.",
        ),
    )


def _configure_agent_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="agent_operation", required=True)
    start_parser = subparsers.add_parser("start", help="start a new interactive coding-agent session")
    _configure_start_parser(start_parser)
    sessions_parser = subparsers.add_parser(
        "sessions",
        help="inspect and manage sensitive durable session records",
        description=(
            "Session records under .fabrica/ are sensitive local artifacts. Add .fabrica/ to .gitignore; "
            "optional .fabricaignore exclusions can reduce normal resume sensitivity."
        ),
    )
    session_subparsers = sessions_parser.add_subparsers(dest="session_operation", required=True)
    list_parser = session_subparsers.add_parser("list", help="list durable session IDs")
    _add_workspace_argument(list_parser)
    inspect_parser = session_subparsers.add_parser("inspect", help="inspect one durable session")
    _add_workspace_argument(inspect_parser)
    _add_session_id_argument(inspect_parser)
    delete_parser = session_subparsers.add_parser("delete", help="delete one durable session")
    _add_workspace_argument(delete_parser)
    _add_session_id_argument(delete_parser)
    export_parser = session_subparsers.add_parser("export", help="export one durable session bundle")
    _add_workspace_argument(export_parser)
    _add_session_id_argument(export_parser)
    export_parser.add_argument(
        "--destination", required=True, type=Path, help="New destination directory for the export."
    )
    resume_parser = session_subparsers.add_parser("resume", help="safely resume one durable session")
    _add_workspace_argument(resume_parser)
    _add_session_id_argument(resume_parser)
    resume_parser.add_argument(
        "--prompt", required=True, type=_parse_prompt, help="Task for the fresh continuation turn."
    )
    resume_parser.add_argument("--skill-root", dest="skill_roots", action="append", default=[], type=Path)


def _configure_start_parser(parser: argparse.ArgumentParser) -> None:
    _add_workspace_argument(parser)
    parser.add_argument("--prompt", required=True, type=_parse_prompt, help="Task for the coding-agent session.")
    parser.add_argument("--skill", dest="skill_ids", action="append", default=[], type=_parse_skill_id)
    parser.add_argument("--resource", dest="resources", action="append", default=[], type=_parse_resource_selection)
    parser.add_argument("--skill-root", dest="skill_roots", action="append", default=[], type=Path)


def _add_workspace_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        dest="workspace_root",
        required=True,
        type=_parse_workspace,
        help="Existing workspace directory.",
    )


def _add_session_id_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("session_id", help="Durable session identifier.")


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
        if namespace.agent_operation == "start":
            command: CodingAgentSessionCliCommand = CliCodingAgentSessionCommand(
                workspace_root=namespace.workspace_root,
                prompt=namespace.prompt,
                skill_ids=tuple(namespace.skill_ids),
                resources=tuple(namespace.resources),
            )
        else:
            command = CliSessionRecordCommand(
                workspace_root=namespace.workspace_root,
                operation=namespace.session_operation,
                session_id=getattr(namespace, "session_id", None),
                prompt=getattr(namespace, "prompt", None),
                export_destination=getattr(namespace, "destination", None),
            )
    except ValueError as err:
        raise UsageError(str(err)) from err
    return _ParsedCodingAgentSessionCommand(
        command=command,
        composition_options=CodingAgentSessionCliCompositionOptions(
            skill_roots=tuple(getattr(namespace, "skill_roots", ())),
        ),
    )


def _handler(
    handler: CodingAgentSessionCliHandler,
) -> Callable[[_ParsedCodingAgentSessionCommand, CommandContext], int]:
    def run(parsed: _ParsedCodingAgentSessionCommand, context: CommandContext) -> int:
        return handler(parsed.command, parsed.composition_options, context)

    return run
