"""Argparse registration for agent-runtime CLI commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Protocol

from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptApprovalOptions,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
    CliSkillRootOptions,
)
from fabrica.features.agent_runtime.application.dtos import SkillScriptType


class CliSubparsers(Protocol):
    """Subparser behavior needed by agent-runtime CLI registration."""

    def add_parser(self, name: str, **kwargs: object) -> argparse.ArgumentParser:
        """Add one named subcommand parser to the product CLI."""


def register_agent_runtime_cli_commands(subparsers: CliSubparsers) -> None:
    """Register agent-runtime owned commands on the product CLI parser."""
    run_parser = subparsers.add_parser(
        "run",
        help="run one local runtime prompt",
        description="Run one local runtime prompt with explicitly selected context only.",
    )
    run_parser.add_argument("--prompt", required=True, help="Prompt text for the local runtime run.")
    run_parser.add_argument("--model", dest="model_hint", help="Optional model hint passed to the runtime.")
    run_parser.add_argument(
        "--skill",
        dest="skill_ids",
        action="append",
        default=[],
        help="Explicit selected Agent Skill ID. May be repeated.",
    )
    run_parser.add_argument(
        "--resource",
        dest="resources",
        action="append",
        type=_parse_resource_selection,
        default=[],
        metavar="SKILL_ID:RESOURCE_ID",
        help="Explicit selected Agent Skill resource. May be repeated.",
    )
    _add_common_skill_root_flags(run_parser)
    run_parser.set_defaults(command_factory=_run_command_from_namespace)

    policy_parser = subparsers.add_parser(
        "script-policy",
        help="inspect selected skill script policy without executing it",
        description="Evaluate policy for one explicitly selected Agent Skill script without executing it.",
    )
    policy_parser.add_argument("--skill-id", required=True, help="Explicit selected Agent Skill ID.")
    policy_parser.add_argument("--script-id", required=True, help="Relative selected script ID within the skill.")
    _add_common_skill_root_flags(policy_parser)
    policy_parser.set_defaults(command_factory=_script_policy_command_from_namespace)

    execute_parser = subparsers.add_parser(
        "script-execute",
        help="execute one explicitly selected skill script with metadata-bound approval",
        description=(
            "Execute one explicitly selected Agent Skill script only when the supplied "
            "non-interactive approval metadata matches the inspected script. This is not production sandboxing."
        ),
    )
    execute_parser.add_argument("--skill-id", required=True, help="Explicit selected Agent Skill ID.")
    execute_parser.add_argument("--script-id", required=True, help="Relative selected script ID within the skill.")
    execute_parser.add_argument(
        "--approve-script-type",
        required=True,
        choices=tuple(script_type.value for script_type in SkillScriptType),
        help="Approved script type bound to the selected script metadata.",
    )
    execute_parser.add_argument(
        "--approve-suffix",
        required=True,
        help="Approved script suffix bound to the selected script metadata, such as .py or .sh.",
    )
    execute_parser.add_argument(
        "--approve-byte-size",
        required=True,
        type=_parse_positive_int,
        help="Approved script byte size bound to the selected script metadata.",
    )
    execute_parser.add_argument(
        "--approve-content-digest",
        required=True,
        help="Approved content digest bound to the selected script metadata, such as sha256:....",
    )
    _add_common_skill_root_flags(execute_parser)
    execute_parser.set_defaults(command_factory=_script_execute_command_from_namespace)


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
    return CliSelectedResource(skill_id=skill_id, resource_id=resource_id)


def _parse_positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        msg = "value must be at least 1"
        raise argparse.ArgumentTypeError(msg)
    return parsed


def _run_command_from_namespace(namespace: argparse.Namespace) -> CliRunCommand:
    return CliRunCommand(
        prompt=namespace.prompt,
        model_hint=namespace.model_hint,
        skill_ids=tuple(namespace.skill_ids),
        resources=tuple(namespace.resources),
        skill_root_options=_skill_root_options_from_namespace(namespace),
    )


def _script_policy_command_from_namespace(namespace: argparse.Namespace) -> CliScriptPolicyCommand:
    return CliScriptPolicyCommand(
        skill_id=namespace.skill_id,
        script_id=namespace.script_id,
        skill_root_options=_skill_root_options_from_namespace(namespace),
    )


def _script_execute_command_from_namespace(namespace: argparse.Namespace) -> CliScriptExecuteCommand:
    return CliScriptExecuteCommand(
        skill_id=namespace.skill_id,
        script_id=namespace.script_id,
        approval_options=CliScriptApprovalOptions(
            script_type=SkillScriptType(namespace.approve_script_type),
            suffix=namespace.approve_suffix,
            byte_size=namespace.approve_byte_size,
            content_digest=namespace.approve_content_digest,
        ),
        skill_root_options=_skill_root_options_from_namespace(namespace),
    )


def _skill_root_options_from_namespace(namespace: argparse.Namespace) -> CliSkillRootOptions:
    return CliSkillRootOptions(skill_roots=tuple(namespace.skill_roots))
