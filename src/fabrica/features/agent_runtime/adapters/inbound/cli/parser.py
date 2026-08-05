"""Parser for the local agent runtime command-line adapter."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from fabrica.features.agent_runtime.application.dtos import SkillScriptType
from fabrica.features.developer_workflow.application.use_cases import DEFAULT_COMMIT_MESSAGE_SKILL_ID


@dataclass(frozen=True, slots=True)
class CliGlobalOptions:
    """Parsed CLI options shared by all subcommands."""

    print_usage: bool = False
    print_prices: bool = False
    verbose_diagnostics: bool = False


@dataclass(frozen=True, slots=True)
class CliSelectedResource:
    """Adapter-local reference to one selected skill resource argument."""

    skill_id: str
    resource_id: str


@dataclass(frozen=True, slots=True)
class CliRunCommand:
    """Parsed CLI arguments for one local runtime prompt run."""

    prompt: str
    model_hint: str | None = None
    skill_ids: tuple[str, ...] = field(default_factory=tuple)
    resources: tuple[CliSelectedResource, ...] = field(default_factory=tuple)
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_ids", tuple(self.skill_ids))
        object.__setattr__(self, "resources", tuple(self.resources))
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


@dataclass(frozen=True, slots=True)
class CliCommitMessageCommand:
    """Parsed CLI arguments for selected-skill commit-message generation."""

    skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    model: str | None = None
    reasoning_effort: str | None = None
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


@dataclass(frozen=True, slots=True)
class CliScriptPolicyCommand:
    """Parsed CLI arguments for selected skill script policy evaluation."""

    skill_id: str
    script_id: str
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


@dataclass(frozen=True, slots=True)
class CliScriptExecuteCommand:
    """Parsed CLI arguments for metadata-approved selected script execution."""

    skill_id: str
    script_id: str
    approval_script_type: SkillScriptType
    approval_suffix: str
    approval_byte_size: int
    approval_content_digest: str
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


type CliCommand = CliRunCommand | CliCommitMessageCommand | CliScriptPolicyCommand | CliScriptExecuteCommand


@dataclass(frozen=True, slots=True)
class CliInvocation:
    """Parsed CLI invocation with shared options and one selected command."""

    command: CliCommand
    global_options: CliGlobalOptions = field(default_factory=CliGlobalOptions)


def build_parser() -> argparse.ArgumentParser:
    """Build the side-effect-free CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="fabrica",
        description="Run local subscription-backed agent runtime experiments.",
    )
    parser.add_argument(
        "--print-usage",
        action="store_true",
        help="Print model usage evidence after command output when available.",
    )
    parser.add_argument(
        "--print-prices",
        action="store_true",
        help="Print model pricing/cost evidence after command output when available.",
    )
    parser.add_argument(
        "--verbose-diagnostics",
        action="store_true",
        help="Include additional diagnostics without exposing secrets or executing scripts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    commit_message_parser = subparsers.add_parser(
        "commit-message",
        help="propose a commit message for staged git changes",
        description="Load the selected commit-message Agent Skill and staged git diff context.",
    )
    commit_message_parser.add_argument(
        "--skill",
        dest="skill_id",
        default=DEFAULT_COMMIT_MESSAGE_SKILL_ID,
        help="Selected commit-message Agent Skill ID. Defaults to conventional-commits.",
    )
    commit_message_parser.add_argument(
        "--model",
        dest="model",
        help="Optional Codex model override for commit-message generation.",
    )
    commit_message_parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max", "ultra"),
        help="Optional Codex reasoning effort override for commit-message generation.",
    )
    _add_common_skill_root_flags(commit_message_parser)
    commit_message_parser.set_defaults(command_factory=_commit_message_command_from_namespace)

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

    return parser


def parse_args(args: tuple[str, ...] | list[str] | None = None) -> CliInvocation:
    """Parse command-line arguments into an adapter-local invocation object."""
    namespace = build_parser().parse_args(args)
    command_factory = namespace.command_factory
    return CliInvocation(
        command=command_factory(namespace),
        global_options=CliGlobalOptions(
            print_usage=namespace.print_usage,
            print_prices=namespace.print_prices,
            verbose_diagnostics=namespace.verbose_diagnostics,
        ),
    )


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
        skill_roots=tuple(namespace.skill_roots),
    )


def _commit_message_command_from_namespace(namespace: argparse.Namespace) -> CliCommitMessageCommand:
    return CliCommitMessageCommand(
        skill_id=namespace.skill_id,
        model=namespace.model,
        reasoning_effort=namespace.reasoning_effort,
        skill_roots=tuple(namespace.skill_roots),
    )


def _script_policy_command_from_namespace(namespace: argparse.Namespace) -> CliScriptPolicyCommand:
    return CliScriptPolicyCommand(
        skill_id=namespace.skill_id,
        script_id=namespace.script_id,
        skill_roots=tuple(namespace.skill_roots),
    )


def _script_execute_command_from_namespace(namespace: argparse.Namespace) -> CliScriptExecuteCommand:
    return CliScriptExecuteCommand(
        skill_id=namespace.skill_id,
        script_id=namespace.script_id,
        approval_script_type=SkillScriptType(namespace.approve_script_type),
        approval_suffix=namespace.approve_suffix,
        approval_byte_size=namespace.approve_byte_size,
        approval_content_digest=namespace.approve_content_digest,
        skill_roots=tuple(namespace.skill_roots),
    )
