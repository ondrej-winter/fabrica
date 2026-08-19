"""Offline integration tests for Agent Skill script execution composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import TYPE_CHECKING

from fabrica.bootstrap import SkillScriptExecutionOptions, create_skill_script_executor
from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptExecutionCommand,
    SkillScriptExecutionStatus,
    SkillScriptType,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class FakeSkillScriptApprovalLookup:
    """In-memory approval lookup for synthetic script execution tests."""

    decisions_by_binding: dict[SkillScriptApprovalBinding, SkillScriptApprovalDecision] = field(default_factory=dict)
    calls: list[SkillScriptApprovalBinding] = field(default_factory=list)

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        """Return a preconfigured approval decision or deny by default."""
        self.calls.append(binding)
        return self.decisions_by_binding.get(
            binding,
            SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.NOT_REQUESTED, binding=binding),
        )


def test_skill_script_execution_composition_executes_approved_synthetic_script(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "python-testing", "scripts/check.py", "print('composition-ok')\n")
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)
    approval_lookup = FakeSkillScriptApprovalLookup(
        decisions_by_binding={
            binding: SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.APPROVED, binding=binding),
        },
    )

    executor = create_skill_script_executor(
        SkillScriptExecutionOptions(skill_roots=(tmp_path,), approval_lookup=approval_lookup),
    )
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))

    assert result.status is SkillScriptExecutionStatus.SUCCESS
    assert result.stdout.text == "composition-ok\n"
    assert result.binding == binding
    assert approval_lookup.calls == [binding]


def test_skill_script_execution_composition_denies_by_default_without_execution(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "python-testing",
        "scripts/write.py",
        "from pathlib import Path\nPath('created.txt').write_text('ran', encoding='utf-8')\n",
    )
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/write.py")
    working_directory = tmp_path / "work"

    executor = create_skill_script_executor(
        SkillScriptExecutionOptions(skill_roots=(tmp_path,), working_directory=working_directory),
    )
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))

    assert result.status is SkillScriptExecutionStatus.POLICY_DENIED
    assert result.binding == _binding(selection, script, SkillScriptType.PYTHON)
    assert not (working_directory / "created.txt").exists()


def test_skill_script_execution_factory_does_not_read_skill_roots_during_construction(tmp_path: Path) -> None:
    missing_skill_root = tmp_path / "missing-skills"

    executor = create_skill_script_executor(
        SkillScriptExecutionOptions(skill_roots=(missing_skill_root,)),
    )

    result = executor.execute(
        SkillScriptExecutionCommand(
            selection=SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py"),
        ),
    )

    assert result.status is SkillScriptExecutionStatus.POLICY_DENIED
    assert result.observations[0].metadata["policy_status"] == "metadata_error"


def test_skill_script_execution_composition_preserves_explicit_empty_skill_roots(tmp_path: Path) -> None:
    """Keep explicit empty roots from widening access to the default skill root."""
    _write_script(tmp_path, "python-testing", "scripts/check.py", "print('must not run')\n")

    executor = create_skill_script_executor(SkillScriptExecutionOptions(skill_roots=()))
    result = executor.execute(
        SkillScriptExecutionCommand(
            selection=SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py"),
        ),
    )

    assert result.status is SkillScriptExecutionStatus.POLICY_DENIED
    assert result.observations[0].metadata["policy_status"] == "metadata_error"


def test_existing_policy_only_helper_remains_inert_when_execution_helper_exists(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "python-testing", "scripts/check.py", "print('not executed')\n")
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)

    executor = create_skill_script_executor(
        SkillScriptExecutionOptions(
            skill_roots=(tmp_path,),
            approval_lookup=FakeSkillScriptApprovalLookup(),
        ),
    )
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))

    assert result.status is SkillScriptExecutionStatus.POLICY_DENIED
    assert result.binding == binding


def _write_script(root: Path, skill_id: str, script_id: str, text: str) -> Path:
    script_file = root / skill_id / script_id
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(text, encoding="utf-8")
    return script_file


def _binding(selection: SelectedSkillScript, script: Path, script_type: SkillScriptType) -> SkillScriptApprovalBinding:
    content = script.read_bytes()
    return SkillScriptApprovalBinding(
        skill_id=selection.skill_id,
        script_id=selection.script_id,
        script_type=script_type,
        suffix=script.suffix,
        byte_size=len(content),
        content_digest=f"sha256:{sha256(content).hexdigest()}",
    )
