"""Tests for selected Agent Skills script policy evaluation."""

from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptMetadata,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyStatus,
    SkillScriptSandboxPolicy,
    SkillScriptType,
)
from fabrica.features.agent_runtime.application.ports import SkillScriptMetadataLoadError
from fabrica.features.agent_runtime.application.use_cases import EvaluateSkillScriptPolicy


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
class FakeSkillScriptApprovalLookup:
    decisions_by_binding: dict[SkillScriptApprovalBinding, SkillScriptApprovalDecision]
    calls: list[SkillScriptApprovalBinding] = field(default_factory=list)

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        self.calls.append(binding)
        return self.decisions_by_binding.get(
            binding,
            SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.NOT_REQUESTED),
        )


def test_evaluate_approves_when_metadata_policy_and_approval_match() -> None:
    selection = _selection()
    binding = _binding()
    metadata_loader = FakeSkillScriptMetadataLoader(
        metadata_by_selection={_selection_key(selection): SkillScriptMetadata(selection=selection, binding=binding)},
    )
    approval_lookup = FakeSkillScriptApprovalLookup(
        decisions_by_binding={
            binding: SkillScriptApprovalDecision(
                status=SkillScriptApprovalStatus.APPROVED,
                binding=binding,
            ),
        },
    )

    result = EvaluateSkillScriptPolicy(metadata_loader, approval_lookup).evaluate(
        SkillScriptPolicyEvaluationCommand(selection=selection),
    )

    assert result.status is SkillScriptPolicyStatus.APPROVED
    assert result.approved is True
    assert result.binding == binding
    assert metadata_loader.calls == [selection]
    assert approval_lookup.calls == [binding]
    assert result.observations[0].metadata == {
        "skill_id": "python-testing",
        "script_id": "scripts/check.py",
        "category": "policy_approved",
    }


def test_evaluate_returns_metadata_error_when_metadata_loading_fails() -> None:
    selection = _selection(script_id="scripts/missing.py")
    metadata_loader = FakeSkillScriptMetadataLoader(metadata_by_selection={})
    approval_lookup = FakeSkillScriptApprovalLookup(decisions_by_binding={})

    result = EvaluateSkillScriptPolicy(metadata_loader, approval_lookup).evaluate(
        SkillScriptPolicyEvaluationCommand(selection=selection),
    )

    assert result.status is SkillScriptPolicyStatus.METADATA_ERROR
    assert result.binding is None
    assert approval_lookup.calls == []
    assert result.observations[0].metadata == {
        "skill_id": "python-testing",
        "script_id": "scripts/missing.py",
        "category": "missing_script_metadata",
    }


def test_evaluate_denies_when_approval_is_absent_denied_or_expired() -> None:
    selection = _selection()
    binding = _binding()
    metadata_loader = FakeSkillScriptMetadataLoader(
        metadata_by_selection={_selection_key(selection): SkillScriptMetadata(selection=selection, binding=binding)},
    )

    for status in (
        SkillScriptApprovalStatus.NOT_REQUESTED,
        SkillScriptApprovalStatus.DENIED,
        SkillScriptApprovalStatus.EXPIRED,
    ):
        approval_lookup = FakeSkillScriptApprovalLookup(
            decisions_by_binding={binding: SkillScriptApprovalDecision(status=status)},
        )

        result = EvaluateSkillScriptPolicy(metadata_loader, approval_lookup).evaluate(
            SkillScriptPolicyEvaluationCommand(selection=selection),
        )

        assert result.status is SkillScriptPolicyStatus.DENIED
        assert result.approved is False
        assert result.observations[0].metadata["category"] == "approval_not_approved"
        assert result.observations[0].metadata["approval_status"] == status.value


def test_evaluate_denies_when_approval_binding_does_not_match_metadata() -> None:
    selection = _selection()
    binding = _binding()
    other_binding = _binding(script_id="scripts/other.py")
    metadata_loader = FakeSkillScriptMetadataLoader(
        metadata_by_selection={_selection_key(selection): SkillScriptMetadata(selection=selection, binding=binding)},
    )
    approval_lookup = FakeSkillScriptApprovalLookup(
        decisions_by_binding={
            binding: SkillScriptApprovalDecision(
                status=SkillScriptApprovalStatus.APPROVED,
                binding=other_binding,
            ),
        },
    )

    result = EvaluateSkillScriptPolicy(metadata_loader, approval_lookup).evaluate(
        SkillScriptPolicyEvaluationCommand(selection=selection),
    )

    assert result.status is SkillScriptPolicyStatus.DENIED
    assert result.observations[0].metadata["category"] == "approval_binding_mismatch"


def test_evaluate_reports_metadata_error_when_loaded_metadata_is_inconsistent() -> None:
    selection = _selection()
    binding = _binding(script_type=SkillScriptType.SHELL)
    metadata_loader = FakeSkillScriptMetadataLoader(
        metadata_by_selection={_selection_key(selection): SkillScriptMetadata(selection=selection, binding=binding)},
    )
    approval_lookup = FakeSkillScriptApprovalLookup(decisions_by_binding={})

    result = EvaluateSkillScriptPolicy(metadata_loader, approval_lookup).evaluate(
        SkillScriptPolicyEvaluationCommand(selection=selection),
    )

    assert result.status is SkillScriptPolicyStatus.METADATA_ERROR
    assert approval_lookup.calls == []
    assert result.observations[0].metadata["category"] == "metadata_script_type_mismatch"


def test_evaluate_rejects_oversized_scripts_before_approval_lookup() -> None:
    selection = _selection()
    binding = _binding(byte_size=129)
    metadata_loader = FakeSkillScriptMetadataLoader(
        metadata_by_selection={_selection_key(selection): SkillScriptMetadata(selection=selection, binding=binding)},
    )
    approval_lookup = FakeSkillScriptApprovalLookup(decisions_by_binding={})

    result = EvaluateSkillScriptPolicy(metadata_loader, approval_lookup).evaluate(
        SkillScriptPolicyEvaluationCommand(
            selection=selection,
            sandbox_policy=SkillScriptSandboxPolicy(max_script_bytes=128),
        ),
    )

    assert result.status is SkillScriptPolicyStatus.POLICY_VIOLATION
    assert approval_lookup.calls == []
    assert result.observations[0].metadata == {
        "skill_id": "python-testing",
        "script_id": "scripts/check.py",
        "category": "script_size_exceeds_policy",
        "byte_size": 129,
        "max_script_bytes": 128,
    }


def test_evaluate_rejects_declarative_network_and_write_access_requests() -> None:
    selection = _selection()
    binding = _binding()
    metadata_loader = FakeSkillScriptMetadataLoader(
        metadata_by_selection={_selection_key(selection): SkillScriptMetadata(selection=selection, binding=binding)},
    )

    for sandbox_policy, expected_category in (
        (SkillScriptSandboxPolicy(allow_network=True), "network_access_not_supported"),
        (SkillScriptSandboxPolicy(writable_path_labels=("workspace",)), "writable_paths_not_supported"),
    ):
        approval_lookup = FakeSkillScriptApprovalLookup(decisions_by_binding={})

        result = EvaluateSkillScriptPolicy(metadata_loader, approval_lookup).evaluate(
            SkillScriptPolicyEvaluationCommand(selection=selection, sandbox_policy=sandbox_policy),
        )

        assert result.status is SkillScriptPolicyStatus.POLICY_VIOLATION
        assert approval_lookup.calls == []
        assert result.observations[0].metadata["category"] == expected_category


def _selection(*, script_id: str = "scripts/check.py") -> SelectedSkillScript:
    return SelectedSkillScript(skill_id="python-testing", script_id=script_id)


def _selection_key(selection: SelectedSkillScript) -> tuple[str, str]:
    return (selection.skill_id, selection.script_id)


def _binding(
    *,
    script_id: str = "scripts/check.py",
    script_type: SkillScriptType = SkillScriptType.PYTHON,
    byte_size: int = 128,
) -> SkillScriptApprovalBinding:
    return SkillScriptApprovalBinding(
        skill_id="python-testing",
        script_id=script_id,
        script_type=script_type,
        suffix=".py",
        byte_size=byte_size,
        content_digest="sha256:abc123",
    )
