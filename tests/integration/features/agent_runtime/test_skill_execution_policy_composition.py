"""Offline integration tests for Agent Skill script policy composition."""

from dataclasses import dataclass, field
from pathlib import Path

from fabrica.bootstrap import (
    SkillScriptPolicyEvaluationOptions,
    create_skill_script_policy_evaluator,
)
from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyStatus,
    SkillScriptSandboxPolicy,
)


@dataclass
class FakeSkillScriptApprovalLookup:
    decisions_by_binding: dict[SkillScriptApprovalBinding, SkillScriptApprovalDecision] = field(default_factory=dict)
    calls: list[SkillScriptApprovalBinding] = field(default_factory=list)

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        self.calls.append(binding)
        return self.decisions_by_binding.get(
            binding,
            SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.NOT_REQUESTED, binding=binding),
        )


def test_skill_script_policy_composition_approves_selected_synthetic_script(tmp_path: Path) -> None:
    _write_script(tmp_path, "python-testing", "scripts/check.py", "print('not executed')\n")
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    approval_lookup = FakeSkillScriptApprovalLookup()
    evaluator = create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=(tmp_path,),
            approval_lookup=approval_lookup,
        ),
    )

    first_result = evaluator.evaluate(SkillScriptPolicyEvaluationCommand(selection=selection))
    assert first_result.status is SkillScriptPolicyStatus.DENIED
    assert first_result.binding is not None

    approval_lookup.decisions_by_binding[first_result.binding] = SkillScriptApprovalDecision(
        status=SkillScriptApprovalStatus.APPROVED,
        binding=first_result.binding,
    )
    approved_result = evaluator.evaluate(SkillScriptPolicyEvaluationCommand(selection=selection))

    assert approved_result.status is SkillScriptPolicyStatus.APPROVED
    assert approved_result.approved is True
    assert approval_lookup.calls == [first_result.binding, first_result.binding]
    assert approved_result.observations[0].metadata == {
        "skill_id": "python-testing",
        "script_id": "scripts/check.py",
        "category": "policy_approved",
    }


def test_skill_script_policy_factory_does_not_read_skill_roots_during_construction(tmp_path: Path) -> None:
    missing_skill_root = tmp_path / "missing-skills"

    evaluator = create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(skill_roots=(missing_skill_root,)),
    )

    result = evaluator.evaluate(
        SkillScriptPolicyEvaluationCommand(
            selection=SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py"),
        ),
    )

    assert result.status is SkillScriptPolicyStatus.METADATA_ERROR
    assert result.observations[0].metadata == {
        "skill_id": "python-testing",
        "script_id": "scripts/check.py",
        "category": "missing_script",
    }


def test_skill_script_policy_composition_denies_by_default_without_approval(tmp_path: Path) -> None:
    _write_script(tmp_path, "shell-testing", "scripts/check.sh", "echo not-executed\n")
    evaluator = create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(skill_roots=(tmp_path,)),
    )

    result = evaluator.evaluate(
        SkillScriptPolicyEvaluationCommand(
            selection=SelectedSkillScript(skill_id="shell-testing", script_id="scripts/check.sh"),
        ),
    )

    assert result.status is SkillScriptPolicyStatus.DENIED
    assert result.binding is not None
    assert result.binding.suffix == ".sh"
    assert result.observations[0].metadata["approval_status"] == SkillScriptApprovalStatus.NOT_REQUESTED.value


def test_skill_script_policy_composition_uses_declared_sandbox_defaults(tmp_path: Path) -> None:
    _write_script(tmp_path, "python-testing", "scripts/check.py", "print('not executed')\n")
    approval_lookup = FakeSkillScriptApprovalLookup()
    evaluator = create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=(tmp_path,),
            sandbox_policy=SkillScriptSandboxPolicy(max_script_bytes=8),
            approval_lookup=approval_lookup,
        ),
    )

    result = evaluator.evaluate(
        SkillScriptPolicyEvaluationCommand(
            selection=SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py"),
            sandbox_policy=SkillScriptSandboxPolicy(max_script_bytes=8),
        ),
    )

    assert result.status is SkillScriptPolicyStatus.METADATA_ERROR
    assert approval_lookup.calls == []
    assert result.observations[0].metadata == {
        "skill_id": "python-testing",
        "script_id": "scripts/check.py",
        "category": "script_size_exceeds_adapter_limit",
    }


def test_skill_script_policy_composition_keeps_safe_diagnostics_by_default(tmp_path: Path) -> None:
    evaluator = create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(skill_roots=(tmp_path,)),
    )

    result = evaluator.evaluate(
        SkillScriptPolicyEvaluationCommand(
            selection=SelectedSkillScript(skill_id="python-testing", script_id="scripts/missing.py"),
        ),
    )

    assert result.status is SkillScriptPolicyStatus.METADATA_ERROR
    assert str(tmp_path) not in str(result.observations)


def _write_script(root: Path, skill_id: str, script_id: str, text: str) -> Path:
    script_file = root / skill_id / script_id
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(text, encoding="utf-8")
    return script_file
