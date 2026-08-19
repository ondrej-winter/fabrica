"""Composition helpers for selected Agent Skill script policy and execution."""

from dataclasses import dataclass, field
from pathlib import Path

from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import DEFAULT_SKILL_ROOT
from fabrica.features.agent_runtime.adapters.outbound.skill_script_file import SkillScriptFileMetadataLoader
from fabrica.features.agent_runtime.adapters.outbound.skill_script_subprocess import (
    SkillScriptSubprocessExecutionSettings,
    SkillScriptSubprocessExecutor,
)
from fabrica.features.agent_runtime.application.dtos import (
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptSandboxPolicy,
)
from fabrica.features.agent_runtime.application.ports import SkillScriptApprovalLookup
from fabrica.features.agent_runtime.application.use_cases import EvaluateSkillScriptPolicy, ExecuteSkillScript


@dataclass(frozen=True, slots=True)
class SkillScriptPolicyEvaluationOptions:
    """Composition options for selected skill script policy evaluation.

    Construction is metadata-loader wiring only; script files are inspected when
    the returned evaluator is called. Without an explicit ``approval_lookup``,
    selected scripts are denied by default in non-interactive runs.
    """

    skill_roots: tuple[Path, ...] | None = None
    sandbox_policy: SkillScriptSandboxPolicy = field(default_factory=SkillScriptSandboxPolicy)
    max_script_bytes: int | None = None
    verbose_diagnostics: bool = False
    approval_lookup: SkillScriptApprovalLookup | None = None


@dataclass(frozen=True, slots=True)
class SkillScriptExecutionOptions:
    """Composition options for selected skill script execution.

    Script execution remains policy-gated. Construction does not inspect skill
    roots or execute scripts; the selected script can run only after evaluation
    returns an approved binding. ``working_directory`` controls subprocess cwd
    and interpreter fields select the command used for approved scripts.
    """

    skill_roots: tuple[Path, ...] | None = None
    sandbox_policy: SkillScriptSandboxPolicy = field(default_factory=SkillScriptSandboxPolicy)
    max_script_bytes: int | None = None
    verbose_diagnostics: bool = False
    approval_lookup: SkillScriptApprovalLookup | None = None
    python_interpreter: str | Path | None = None
    shell_interpreter: str | Path = "/bin/sh"
    working_directory: Path | None = None


class DenyByDefaultSkillScriptApprovalLookup:
    """Non-interactive approval lookup that denies every selected script."""

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        """Return a deterministic absence-of-approval decision."""
        return SkillScriptApprovalDecision(
            status=SkillScriptApprovalStatus.NOT_REQUESTED,
            binding=binding,
        )


def create_skill_script_policy_evaluator(
    options: SkillScriptPolicyEvaluationOptions | None = None,
) -> EvaluateSkillScriptPolicy:
    """Create a use case for selected Agent Skill script policy evaluation.

    The helper wires read-only metadata inspection and a non-interactive approval
    dependency at the composition root. Construction does not read skill roots,
    read Codex credentials, call backends, prompt for approval, or execute
    scripts.
    """
    policy_options = options or SkillScriptPolicyEvaluationOptions()
    sandbox_policy = policy_options.sandbox_policy
    max_script_bytes = (
        sandbox_policy.max_script_bytes if policy_options.max_script_bytes is None else policy_options.max_script_bytes
    )
    return EvaluateSkillScriptPolicy(
        metadata_loader=SkillScriptFileMetadataLoader(
            skill_roots=policy_options.skill_roots,
            max_script_bytes=max_script_bytes,
            verbose_diagnostics=policy_options.verbose_diagnostics,
        ),
        approval_lookup=policy_options.approval_lookup or DenyByDefaultSkillScriptApprovalLookup(),
    )


def create_skill_script_executor(
    options: SkillScriptExecutionOptions | None = None,
) -> ExecuteSkillScript:
    """Create a policy-gated use case for selected Agent Skill script execution.

    The helper wires metadata inspection, non-interactive approval lookup, policy
    evaluation, and constrained subprocess execution. Construction does not read
    skill roots, execute scripts, prompt for approval, read Codex credentials, or
    call backends.
    """
    execution_options = options or SkillScriptExecutionOptions()
    skill_roots = (DEFAULT_SKILL_ROOT,) if execution_options.skill_roots is None else execution_options.skill_roots
    max_script_bytes = (
        execution_options.sandbox_policy.max_script_bytes
        if execution_options.max_script_bytes is None
        else execution_options.max_script_bytes
    )
    policy_evaluator = create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=skill_roots,
            sandbox_policy=execution_options.sandbox_policy,
            max_script_bytes=max_script_bytes,
            verbose_diagnostics=execution_options.verbose_diagnostics,
            approval_lookup=execution_options.approval_lookup,
        ),
    )
    executor = SkillScriptSubprocessExecutor(
        snapshot_loader=SkillScriptFileMetadataLoader(
            skill_roots=skill_roots,
            max_script_bytes=max_script_bytes,
            verbose_diagnostics=execution_options.verbose_diagnostics,
        ),
        settings=SkillScriptSubprocessExecutionSettings(
            python_interpreter=execution_options.python_interpreter,
            shell_interpreter=execution_options.shell_interpreter,
            working_directory=execution_options.working_directory,
            verbose_diagnostics=execution_options.verbose_diagnostics,
        ),
    )
    return ExecuteSkillScript(policy_evaluator=policy_evaluator, executor=executor)
