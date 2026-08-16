"""Argparse registration for agent-runtime CLI commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli import CliCommandSpec
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    AgentRuntimeCliCompositionOptions,
    CliRunCommand,
    CliScriptApprovalOptions,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SelectedSkill,
    SelectedSkillResource,
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptType,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from fabrica.adapters.inbound.cli import CliCommandRegistry, CliExecutionContext

RUN_COMMAND_NAME = "run"
SCRIPT_POLICY_COMMAND_NAME = "script-policy"
SCRIPT_EXECUTE_COMMAND_NAME = "script-execute"
AGENT_RUNTIME_CLI_COMMAND_NAMES = (RUN_COMMAND_NAME, SCRIPT_POLICY_COMMAND_NAME, SCRIPT_EXECUTE_COMMAND_NAME)
type AgentRuntimeCliHandler[TCommand] = Callable[
    [TCommand, AgentRuntimeCliCompositionOptions, CliExecutionContext], int
]


@dataclass(frozen=True, slots=True)
class _ParsedAgentRuntimeCliCommand[TCommand]:
    command: TCommand
    composition_options: AgentRuntimeCliCompositionOptions


def register_agent_runtime_cli_commands(
    commands: CliCommandRegistry,
    *,
    run_command: AgentRuntimeCliHandler[CliRunCommand],
    script_policy_command: AgentRuntimeCliHandler[CliScriptPolicyCommand],
    script_execute_command: AgentRuntimeCliHandler[CliScriptExecuteCommand],
) -> None:
    """Register agent-runtime owned commands on the product CLI parser."""
    commands.register(
        CliCommandSpec(
            name=RUN_COMMAND_NAME,
            summary="run one local runtime prompt",
            configure_parser=_configure_run_parser,
            decode=_parsed_run_command_from_namespace,
            handler=_handler_for_run_command(run_command),
            description="Run one local runtime prompt with explicitly selected context only.",
        ),
    )

    commands.register(
        CliCommandSpec(
            name=SCRIPT_POLICY_COMMAND_NAME,
            summary="inspect selected skill script policy without executing it",
            configure_parser=_configure_script_policy_parser,
            decode=_parsed_script_policy_command_from_namespace,
            handler=_handler_for_script_policy_command(script_policy_command),
            description="Evaluate policy for one explicitly selected Agent Skill script without executing it.",
        ),
    )

    commands.register(
        CliCommandSpec(
            name=SCRIPT_EXECUTE_COMMAND_NAME,
            summary="execute one explicitly selected skill script with metadata-bound approval",
            configure_parser=_configure_script_execute_parser,
            decode=_parsed_script_execute_command_from_namespace,
            handler=_handler_for_script_execute_command(script_execute_command),
            description=(
                "Execute one explicitly selected Agent Skill script only when the supplied "
                "non-interactive approval metadata matches the inspected script. This is not production sandboxing."
            ),
        ),
    )


def _configure_run_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--prompt",
        required=True,
        type=_parse_prompt,
        help="Prompt text for the local runtime run.",
    )
    parser.add_argument(
        "--skill",
        dest="skill_ids",
        action="append",
        type=_parse_skill_id,
        default=[],
        help="Explicit selected Agent Skill ID. May be repeated.",
    )
    parser.add_argument(
        "--resource",
        dest="resources",
        action="append",
        type=_parse_resource_selection,
        default=[],
        metavar="SKILL_ID:RESOURCE_ID",
        help="Explicit selected Agent Skill resource. May be repeated.",
    )
    _add_common_skill_root_flags(parser)


def _configure_script_policy_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skill-id",
        required=True,
        type=_parse_skill_id,
        help="Explicit selected Agent Skill ID.",
    )
    parser.add_argument(
        "--script-id",
        required=True,
        type=_parse_script_id,
        help="Relative selected script ID within the skill.",
    )
    _add_common_skill_root_flags(parser)


def _configure_script_execute_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skill-id",
        required=True,
        type=_parse_skill_id,
        help="Explicit selected Agent Skill ID.",
    )
    parser.add_argument(
        "--script-id",
        required=True,
        type=_parse_script_id,
        help="Relative selected script ID within the skill.",
    )
    parser.add_argument(
        "--approve-script-type",
        required=True,
        choices=tuple(script_type.value for script_type in SkillScriptType),
        help="Approved script type bound to the selected script metadata.",
    )
    parser.add_argument(
        "--approve-suffix",
        required=True,
        type=_parse_approved_suffix,
        help="Approved script suffix bound to the selected script metadata, such as .py or .sh.",
    )
    parser.add_argument(
        "--approve-byte-size",
        required=True,
        type=_parse_positive_int,
        help="Approved script byte size bound to the selected script metadata.",
    )
    parser.add_argument(
        "--approve-content-digest",
        required=True,
        type=_parse_content_digest,
        help="Approved content digest bound to the selected script metadata, such as sha256:....",
    )
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


def _parse_resource_selection(value: str) -> CliSelectedResource:
    skill_id, separator, resource_id = value.partition(":")
    if not separator or not skill_id or not resource_id:
        msg = "resource must use SKILL_ID:RESOURCE_ID"
        raise argparse.ArgumentTypeError(msg)
    try:
        SelectedSkillResource(skill_id=skill_id, resource_id=resource_id)
    except ValueError as err:
        raise _argument_type_error(err) from err
    return CliSelectedResource(skill_id=skill_id, resource_id=resource_id)


def _parse_prompt(value: str) -> str:
    try:
        LocalAgentRunCommand(prompt=value)
    except ValueError as err:
        raise _argument_type_error(err) from err
    return value


def _parse_skill_id(value: str) -> str:
    try:
        SelectedSkill(skill_id=value)
    except ValueError as err:
        raise _argument_type_error(err) from err
    if value.startswith("/") or "//" in value:
        msg = "skill_id must be a relative identifier"
        raise argparse.ArgumentTypeError(msg)
    if any(part in {"", ".", ".."} for part in value.split("/")):
        msg = "skill_id must not contain traversal segments"
        raise argparse.ArgumentTypeError(msg)
    return value


def _parse_script_id(value: str) -> str:
    try:
        SelectedSkillScript(skill_id="selected-skill", script_id=value)
    except ValueError as err:
        raise _argument_type_error(err) from err
    return value


def _parse_approved_suffix(value: str) -> str:
    try:
        SkillScriptApprovalBinding(
            skill_id="selected-skill",
            script_id="scripts/selected.py",
            script_type=SkillScriptType.PYTHON,
            suffix=value,
            byte_size=1,
            content_digest="sha256:synthetic",
        )
    except ValueError as err:
        raise _argument_type_error(err) from err
    return value


def _parse_content_digest(value: str) -> str:
    try:
        SkillScriptApprovalBinding(
            skill_id="selected-skill",
            script_id="scripts/selected.py",
            script_type=SkillScriptType.PYTHON,
            suffix=".py",
            byte_size=1,
            content_digest=value,
        )
    except ValueError as err:
        raise _argument_type_error(err) from err
    return value


def _parse_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as err:
        raise _argument_type_error(err) from err
    if parsed < 1:
        msg = "value must be at least 1"
        raise argparse.ArgumentTypeError(msg)
    return parsed


def _argument_type_error(error: ValueError) -> argparse.ArgumentTypeError:
    return argparse.ArgumentTypeError(str(error))


def _run_command_from_namespace(namespace: argparse.Namespace) -> CliRunCommand:
    return CliRunCommand(
        prompt=namespace.prompt,
        skill_ids=tuple(namespace.skill_ids),
        resources=tuple(namespace.resources),
    )


def _script_policy_command_from_namespace(namespace: argparse.Namespace) -> CliScriptPolicyCommand:
    return CliScriptPolicyCommand(
        skill_id=namespace.skill_id,
        script_id=namespace.script_id,
    )


def _script_execute_command_from_namespace(namespace: argparse.Namespace) -> CliScriptExecuteCommand:
    approval_binding = SkillScriptApprovalBinding(
        skill_id=namespace.skill_id,
        script_id=namespace.script_id,
        script_type=SkillScriptType(namespace.approve_script_type),
        suffix=namespace.approve_suffix,
        byte_size=namespace.approve_byte_size,
        content_digest=namespace.approve_content_digest,
    )
    return CliScriptExecuteCommand(
        skill_id=namespace.skill_id,
        script_id=namespace.script_id,
        approval_options=CliScriptApprovalOptions(
            script_type=approval_binding.script_type,
            suffix=approval_binding.suffix,
            byte_size=approval_binding.byte_size,
            content_digest=approval_binding.content_digest,
        ),
        approval_binding=approval_binding,
    )


def _parsed_run_command_from_namespace(namespace: argparse.Namespace) -> _ParsedAgentRuntimeCliCommand[CliRunCommand]:
    return _ParsedAgentRuntimeCliCommand(
        command=_run_command_from_namespace(namespace),
        composition_options=_agent_runtime_composition_options_from_namespace(namespace),
    )


def _parsed_script_policy_command_from_namespace(
    namespace: argparse.Namespace,
) -> _ParsedAgentRuntimeCliCommand[CliScriptPolicyCommand]:
    return _ParsedAgentRuntimeCliCommand(
        command=_script_policy_command_from_namespace(namespace),
        composition_options=_agent_runtime_composition_options_from_namespace(namespace),
    )


def _parsed_script_execute_command_from_namespace(
    namespace: argparse.Namespace,
) -> _ParsedAgentRuntimeCliCommand[CliScriptExecuteCommand]:
    return _ParsedAgentRuntimeCliCommand(
        command=_script_execute_command_from_namespace(namespace),
        composition_options=_agent_runtime_composition_options_from_namespace(namespace),
    )


def _handler_for_run_command(
    handler: AgentRuntimeCliHandler[CliRunCommand],
) -> Callable[[_ParsedAgentRuntimeCliCommand[CliRunCommand], CliExecutionContext], int]:
    def run(parsed: _ParsedAgentRuntimeCliCommand[CliRunCommand], context: CliExecutionContext) -> int:
        return handler(
            parsed.command,
            parsed.composition_options,
            context,
        )

    return run


def _handler_for_script_policy_command(
    handler: AgentRuntimeCliHandler[CliScriptPolicyCommand],
) -> Callable[[_ParsedAgentRuntimeCliCommand[CliScriptPolicyCommand], CliExecutionContext], int]:
    def run(parsed: _ParsedAgentRuntimeCliCommand[CliScriptPolicyCommand], context: CliExecutionContext) -> int:
        return handler(
            parsed.command,
            parsed.composition_options,
            context,
        )

    return run


def _handler_for_script_execute_command(
    handler: AgentRuntimeCliHandler[CliScriptExecuteCommand],
) -> Callable[[_ParsedAgentRuntimeCliCommand[CliScriptExecuteCommand], CliExecutionContext], int]:
    def run(parsed: _ParsedAgentRuntimeCliCommand[CliScriptExecuteCommand], context: CliExecutionContext) -> int:
        return handler(
            parsed.command,
            parsed.composition_options,
            context,
        )

    return run


def _agent_runtime_composition_options_from_namespace(
    namespace: argparse.Namespace,
) -> AgentRuntimeCliCompositionOptions:
    return AgentRuntimeCliCompositionOptions(skill_roots=tuple(namespace.skill_roots))
