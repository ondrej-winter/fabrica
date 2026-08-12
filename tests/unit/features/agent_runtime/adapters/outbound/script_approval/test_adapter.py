"""Tests for metadata-bound script approval lookup adapters."""

from fabrica.features.agent_runtime.adapters.outbound.script_approval import MetadataBoundApprovalLookup
from fabrica.features.agent_runtime.application.dtos import (
    SkillScriptApprovalBinding,
    SkillScriptApprovalStatus,
    SkillScriptType,
)


def test_metadata_bound_approval_lookup_approves_exact_expected_binding() -> None:
    binding = _binding()

    decision = MetadataBoundApprovalLookup(expected_binding=binding).get_approval(binding)

    assert decision.status is SkillScriptApprovalStatus.APPROVED
    assert decision.binding == binding
    assert decision.reason is None


def test_metadata_bound_approval_lookup_denies_mismatched_binding() -> None:
    expected_binding = _binding()
    selected_binding = _binding(content_digest="sha256:changed")

    decision = MetadataBoundApprovalLookup(expected_binding=expected_binding).get_approval(selected_binding)

    assert decision.status is SkillScriptApprovalStatus.DENIED
    assert decision.binding == selected_binding
    assert decision.reason == "approval metadata did not match selected script metadata"


def _binding(*, content_digest: str = "sha256:abc123") -> SkillScriptApprovalBinding:
    return SkillScriptApprovalBinding(
        skill_id="python-testing",
        script_id="scripts/check.py",
        script_type=SkillScriptType.PYTHON,
        suffix=".py",
        byte_size=128,
        content_digest=content_digest,
    )
