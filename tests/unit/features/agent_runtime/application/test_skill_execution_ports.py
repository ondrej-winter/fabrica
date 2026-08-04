"""Tests for selected Agent Skills script policy port contracts."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptExecutionCommand,
    SkillScriptExecutionObservation,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptMetadata,
    SkillScriptType,
)
from fabrica.features.agent_runtime.application.ports import (
    SkillScriptApprovalLookup,
    SkillScriptExecutionError,
    SkillScriptExecutor,
    SkillScriptMetadataLoader,
    SkillScriptMetadataLoadError,
)


@dataclass
class FakeSkillScriptApprovalLookup:
    decisions_by_binding: dict[SkillScriptApprovalBinding, SkillScriptApprovalDecision]
    calls: list[SkillScriptApprovalBinding] = field(default_factory=list)

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        self.calls.append(binding)
        return self.decisions_by_binding.get(
            binding,
            SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.NOT_REQUESTED),
        )


@dataclass
class FakeSkillScriptMetadataLoader:
    metadata_by_selection: dict[tuple[str, str], SkillScriptMetadata]
    calls: list[SelectedSkillScript] = field(default_factory=list)

    def load_metadata(self, selection: SelectedSkillScript) -> SkillScriptMetadata:
        self.calls.append(selection)
        try:
            return self.metadata_by_selection[(selection.skill_id, selection.script_id)]
        except KeyError as err:
            msg = "selected skill script metadata is unavailable"
            raise SkillScriptMetadataLoadError(
                msg,
                skill_id=selection.skill_id,
                script_id=selection.script_id,
                category="missing_script_metadata",
                metadata={"script_id": selection.script_id},
            ) from err


@dataclass
class FakeSkillScriptExecutor:
    results_by_binding: dict[SkillScriptApprovalBinding, SkillScriptExecutionResult]
    calls: list[tuple[SkillScriptExecutionCommand, SkillScriptApprovalBinding]] = field(default_factory=list)

    def execute(
        self,
        command: SkillScriptExecutionCommand,
        approved_binding: SkillScriptApprovalBinding,
    ) -> SkillScriptExecutionResult:
        self.calls.append((command, approved_binding))
        try:
            return self.results_by_binding[approved_binding]
        except KeyError as err:
            msg = "selected skill script execution failed unexpectedly"
            raise SkillScriptExecutionError(
                msg,
                skill_id=command.selection.skill_id,
                script_id=command.selection.script_id,
                category="missing_execution_result",
                metadata={"script_id": command.selection.script_id},
            ) from err


def test_approval_lookup_port_supports_non_interactive_decision_fakes() -> None:
    binding = _binding()
    expected = SkillScriptApprovalDecision(
        status=SkillScriptApprovalStatus.APPROVED,
        binding=binding,
        reason="approved by fixture",
    )
    lookup: SkillScriptApprovalLookup = FakeSkillScriptApprovalLookup(decisions_by_binding={binding: expected})

    decision = lookup.get_approval(binding)

    assert decision == expected


def test_approval_lookup_port_can_report_absent_approval_without_prompting() -> None:
    binding = _binding()
    fake = FakeSkillScriptApprovalLookup(decisions_by_binding={})
    lookup: SkillScriptApprovalLookup = fake

    decision = lookup.get_approval(binding)

    assert decision == SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.NOT_REQUESTED)
    assert fake.calls == [binding]


def test_script_metadata_loader_port_supports_selected_script_metadata_fakes() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    expected = SkillScriptMetadata(
        selection=selection,
        binding=_binding(),
        metadata={"file_name": "check.py"},
    )
    loader: SkillScriptMetadataLoader = FakeSkillScriptMetadataLoader(
        metadata_by_selection={("python-testing", "scripts/check.py"): expected},
    )

    metadata = loader.load_metadata(selection)

    assert metadata == expected


def test_script_metadata_loader_failure_is_application_safe() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/missing.py")
    loader = FakeSkillScriptMetadataLoader(metadata_by_selection={})

    with pytest.raises(SkillScriptMetadataLoadError) as exc_info:
        loader.load_metadata(selection)

    assert str(exc_info.value) == "selected skill script metadata is unavailable"
    assert exc_info.value.skill_id == "python-testing"
    assert exc_info.value.script_id == "scripts/missing.py"
    assert exc_info.value.category == "missing_script_metadata"
    assert exc_info.value.metadata == {"script_id": "scripts/missing.py"}


def test_script_executor_port_supports_approved_execution_fakes() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    command = SkillScriptExecutionCommand(selection=selection)
    binding = _binding()
    expected = SkillScriptExecutionResult(
        status=SkillScriptExecutionStatus.SUCCESS,
        selection=selection,
        binding=binding,
        exit_code=0,
        observations=(SkillScriptExecutionObservation(message="script executed"),),
    )
    fake = FakeSkillScriptExecutor(results_by_binding={binding: expected})
    executor: SkillScriptExecutor = fake

    result = executor.execute(command, binding)

    assert result == expected
    assert fake.calls == [(command, binding)]


def test_script_executor_failure_is_application_safe() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    command = SkillScriptExecutionCommand(selection=selection)
    executor = FakeSkillScriptExecutor(results_by_binding={})

    with pytest.raises(SkillScriptExecutionError) as exc_info:
        executor.execute(command, _binding())

    assert str(exc_info.value) == "selected skill script execution failed unexpectedly"
    assert exc_info.value.skill_id == "python-testing"
    assert exc_info.value.script_id == "scripts/check.py"
    assert exc_info.value.category == "missing_execution_result"
    assert exc_info.value.metadata == {"script_id": "scripts/check.py"}


def _binding() -> SkillScriptApprovalBinding:
    return SkillScriptApprovalBinding(
        skill_id="python-testing",
        script_id="scripts/check.py",
        script_type=SkillScriptType.PYTHON,
        suffix=".py",
        byte_size=128,
        content_digest="sha256:abc123",
    )
