"""Agent-runtime command registration for the product CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.output import (
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    SelectedSkill,
    SelectedSkillResource,
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptExecutionCommand,
    SkillScriptExecutionResult,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyEvaluationResult,
    SkillScriptType,
)

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.options import CliGlobalOptions


class LocalAgentRuntime(Protocol):
    """Protocol for the runtime use case consumed by the CLI adapter."""

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command."""


class CommandAugmenter(Protocol):
    """Protocol for selected skill/resource command augmentation."""

    def __call__(
        self,
        command: LocalAgentRunCommand,
        skill_selections: tuple[SelectedSkill, ...],
        resource_selections: tuple[SelectedSkillResource, ...],
        *,
        skill_roots: tuple[Path, ...],
        verbose_diagnostics: bool,
    ) -> LocalAgentRunCommand:
        """Return a command augmented with explicitly selected context."""


class ScriptPolicyEvaluator(Protocol):
    """Protocol for selected skill script policy evaluation consumed by the CLI adapter."""

    def evaluate(self, command: SkillScriptPolicyEvaluationCommand) -> SkillScriptPolicyEvaluationResult:
        """Evaluate selected script policy without executing the script."""


class ScriptExecutor(Protocol):
    """Protocol for selected skill script execution consumed by the CLI adapter."""

    def execute(self, command: SkillScriptExecutionCommand) -> SkillScriptExecutionResult:
        """Execute one selected skill script through policy-gated application boundaries."""


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


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliDependencies:
    """Injected dependencies for agent-runtime CLI commands."""

    runtime: LocalAgentRuntime | None = None
    command_augmenter: CommandAugmenter | None = None
    script_policy_evaluator: ScriptPolicyEvaluator | None = None
    script_executor: ScriptExecutor | None = None


def register_agent_runtime_cli_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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


def run_agent_runtime_cli_command(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
    dependencies: AgentRuntimeCliDependencies,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run one agent-runtime owned CLI command."""
    if isinstance(command, CliScriptPolicyCommand):
        return _run_script_policy_command(
            command,
            global_options=global_options,
            script_policy_evaluator=dependencies.script_policy_evaluator,
            stdout=stdout,
            stderr=stderr,
        )
    if isinstance(command, CliScriptExecuteCommand):
        return _run_script_execute_command(
            command,
            global_options=global_options,
            script_executor=dependencies.script_executor,
            stdout=stdout,
            stderr=stderr,
        )
    runtime_command = LocalAgentRunCommand(prompt=command.prompt, model_hint=command.model_hint)
    if command.skill_ids or command.resources:
        runtime_command = _augment_command(
            runtime_command,
            command,
            global_options=global_options,
            command_augmenter=dependencies.command_augmenter,
        )
    active_runtime = dependencies.runtime or _create_default_runtime()
    result = active_runtime.run(runtime_command)
    return write_run_result(result, stdout=stdout, stderr=stderr)


def _run_script_policy_command(
    command: CliScriptPolicyCommand,
    *,
    global_options: CliGlobalOptions,
    script_policy_evaluator: ScriptPolicyEvaluator | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    evaluator = script_policy_evaluator or _create_default_script_policy_evaluator(
        command, global_options=global_options
    )
    result = evaluator.evaluate(SkillScriptPolicyEvaluationCommand(selection=selection))
    return write_script_policy_result(result, stdout=stdout, stderr=stderr)


def _run_script_execute_command(
    command: CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
    script_executor: ScriptExecutor | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    executor = script_executor or _create_default_script_executor(command, global_options=global_options)
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))
    return write_script_execution_result(result, stdout=stdout, stderr=stderr)


def _augment_command(
    runtime_command: LocalAgentRunCommand,
    command: CliRunCommand,
    *,
    global_options: CliGlobalOptions,
    command_augmenter: CommandAugmenter | None,
) -> LocalAgentRunCommand:
    skill_selections = tuple(SelectedSkill(skill_id=skill_id) for skill_id in command.skill_ids)
    resource_selections = tuple(
        SelectedSkillResource(skill_id=resource.skill_id, resource_id=resource.resource_id)
        for resource in command.resources
    )
    augmenter = command_augmenter or _default_augment_command
    return augmenter(
        runtime_command,
        skill_selections,
        resource_selections,
        skill_roots=command.skill_roots,
        verbose_diagnostics=global_options.verbose_diagnostics,
    )


def _default_augment_command(
    command: LocalAgentRunCommand,
    skill_selections: tuple[SelectedSkill, ...],
    resource_selections: tuple[SelectedSkillResource, ...],
    *,
    skill_roots: tuple[Path, ...],
    verbose_diagnostics: bool,
) -> LocalAgentRunCommand:
    from fabrica.bootstrap import (  # noqa: PLC0415
        SkillContextAugmentationOptions,
        create_skill_context_augmented_local_agent_command,
    )

    return create_skill_context_augmented_local_agent_command(
        command,
        SkillContextAugmentationOptions(
            skill_selections=skill_selections,
            resource_selections=resource_selections,
            skill_roots=skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
    )


def _create_default_runtime() -> LocalAgentRuntime:
    from fabrica.bootstrap import create_codex_runtime  # noqa: PLC0415

    return create_codex_runtime()


def _create_default_script_policy_evaluator(
    command: CliScriptPolicyCommand,
    *,
    global_options: CliGlobalOptions,
) -> ScriptPolicyEvaluator:
    from fabrica.bootstrap import (  # noqa: PLC0415
        SkillScriptPolicyEvaluationOptions,
        create_skill_script_policy_evaluator,
    )

    return create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=command.skill_roots,
            verbose_diagnostics=global_options.verbose_diagnostics,
        ),
    )


def _create_default_script_executor(
    command: CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
) -> ScriptExecutor:
    from fabrica.bootstrap import (  # noqa: PLC0415
        SkillScriptExecutionOptions,
        create_skill_script_executor,
    )

    return create_skill_script_executor(
        SkillScriptExecutionOptions(
            skill_roots=command.skill_roots,
            verbose_diagnostics=global_options.verbose_diagnostics,
            approval_lookup=_MetadataBoundCliApprovalLookup(command),
        ),
    )


@dataclass(frozen=True, slots=True)
class _MetadataBoundCliApprovalLookup:
    """CLI approval lookup that approves only an exact supplied metadata binding."""

    command: CliScriptExecuteCommand

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        expected = SkillScriptApprovalBinding(
            skill_id=self.command.skill_id,
            script_id=self.command.script_id,
            script_type=self.command.approval_script_type,
            suffix=self.command.approval_suffix,
            byte_size=self.command.approval_byte_size,
            content_digest=self.command.approval_content_digest,
        )
        if binding == expected:
            return SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.APPROVED, binding=binding)
        return SkillScriptApprovalDecision(
            status=SkillScriptApprovalStatus.DENIED,
            binding=binding,
            reason="CLI approval metadata did not match selected script metadata",
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
