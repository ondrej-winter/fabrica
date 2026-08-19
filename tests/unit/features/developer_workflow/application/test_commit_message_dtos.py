"""Tests for evidence-first commit-message DTOs."""

from dataclasses import FrozenInstanceError

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_COMMIT_MESSAGE_SKILL_ID,
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    GenerateCommitMessageResult,
    GitStagedDiff,
    GitStagedFile,
    GitStagedFileStatus,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)


def test_analyze_staged_file_command_reuses_staged_git_boundary_dtos() -> None:
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    diff = GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+change\n")

    command = AnalyzeStagedFileForCommitMessageCommand(staged_file=staged_file, diff=diff)

    assert command.staged_file is staged_file
    assert command.diff is diff


def test_staged_file_commit_evidence_normalizes_required_structured_fields() -> None:
    evidence = _evidence(summary="  Adds commit-message DTOs.  ", impact="  application boundary  ")

    assert evidence.summary == "Adds commit-message DTOs."
    assert evidence.category == "architecture"
    assert evidence.public_contract_impact == "New application DTO contract."
    assert evidence.validation_relevance == "DTO validation tests cover required fields."
    assert evidence.migration_concern == "No migration needed."
    assert evidence.breaking_risk == "No breaking risk identified."
    assert evidence.impact == "application boundary"


@pytest.mark.parametrize(
    "field_name",
    [
        "summary",
        "category",
        "public_contract_impact",
        "validation_relevance",
        "migration_concern",
        "breaking_risk",
    ],
)
def test_staged_file_commit_evidence_rejects_empty_required_text(field_name: str) -> None:
    kwargs = {field_name: "\n"}

    with pytest.raises(ValueError, match=f"{field_name} must not be empty"):
        _evidence(**kwargs)


def test_staged_file_commit_evidence_rejects_empty_optional_impact() -> None:
    with pytest.raises(ValueError, match="impact must not be empty when provided"):
        _evidence(impact=" ")


def test_evidence_bundle_preserves_order_and_serializes_safe_structured_evidence() -> None:
    first = _evidence(path="src/file.py", status=GitStagedFileStatus.MODIFIED, summary="Updates application DTOs.")
    second = _evidence(path="tests/test_file.py", status=GitStagedFileStatus.ADDED, summary="Adds DTO tests.")

    bundle = CommitMessageEvidenceBundle(evidence=(first, second))

    assert bundle.evidence == (first, second)
    assert bundle.serialized_text == (
        "File 1: src/file.py\n"
        "Status: M\n"
        "Category: architecture\n"
        "Summary: Updates application DTOs.\n"
        "Public contract impact: New application DTO contract.\n"
        "Validation relevance: DTO validation tests cover required fields.\n"
        "Migration concern: No migration needed.\n"
        "Breaking risk: No breaking risk identified.\n\n"
        "File 2: tests/test_file.py\n"
        "Status: A\n"
        "Category: architecture\n"
        "Summary: Adds DTO tests.\n"
        "Public contract impact: New application DTO contract.\n"
        "Validation relevance: DTO validation tests cover required fields.\n"
        "Migration concern: No migration needed.\n"
        "Breaking risk: No breaking risk identified."
    )


def test_evidence_bundle_rejects_empty_bundle_and_invalid_bound() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        CommitMessageEvidenceBundle(evidence=())

    with pytest.raises(ValueError, match="at least 1"):
        CommitMessageEvidenceBundle(evidence=(_evidence(),), max_serialized_chars=0)


def test_evidence_bundle_rejects_oversized_serialized_evidence() -> None:
    with pytest.raises(ValueError, match="serialized evidence bound"):
        CommitMessageEvidenceBundle(evidence=(_evidence(),), max_serialized_chars=10)


def test_synthesize_command_defaults_to_conventional_commits_skill_and_accepts_skill_markdown() -> None:
    bundle = CommitMessageEvidenceBundle(evidence=(_evidence(),))

    command = SynthesizeCommitMessageCommand(evidence_bundle=bundle, skill_markdown="  # Skill  ")

    assert command.evidence_bundle is bundle
    assert command.skill_id == DEFAULT_COMMIT_MESSAGE_SKILL_ID
    assert command.skill_markdown == "# Skill"


@pytest.mark.parametrize(
    ("field_name", "kwargs"), [("skill_id", {"skill_id": " "}), ("skill_markdown", {"skill_markdown": " "})]
)
def test_synthesize_command_rejects_empty_text(field_name: str, kwargs: dict[str, str]) -> None:
    bundle = CommitMessageEvidenceBundle(evidence=(_evidence(),))

    with pytest.raises(ValueError, match=field_name):
        SynthesizeCommitMessageCommand(evidence_bundle=bundle, **kwargs)


def test_commit_message_recommendation_and_workflow_result_are_immutable_boundary_values() -> None:
    bundle = CommitMessageEvidenceBundle(evidence=(_evidence(),))
    recommendation = CommitMessageRecommendation(
        summary="Adds evidence DTOs.",
        rationale="The primary change is a new application contract.",
        commit_message="feat(developer-workflow): add commit message evidence DTOs",
    )
    result = GenerateCommitMessageResult(recommendation=recommendation, evidence_bundle=bundle)

    assert result.recommendation is recommendation
    assert result.evidence_bundle is bundle
    with pytest.raises(FrozenInstanceError):
        recommendation.summary = "changed"  # ty: ignore[invalid-assignment]


@pytest.mark.parametrize("field_name", ["summary", "rationale", "commit_message"])
def test_commit_message_recommendation_rejects_empty_required_text(field_name: str) -> None:
    kwargs = {
        "summary": "Summary.",
        "rationale": "Rationale.",
        "commit_message": "feat: add thing",
        field_name: " ",
    }

    with pytest.raises(ValueError, match=f"{field_name} must not be empty"):
        CommitMessageRecommendation(**kwargs)


def _evidence(
    **overrides: object,
) -> StagedFileCommitEvidence:
    values = {
        "path": "src/file.py",
        "status": GitStagedFileStatus.MODIFIED,
        "summary": "Adds evidence-first commit-message DTOs.",
        "category": "architecture",
        "public_contract_impact": "New application DTO contract.",
        "validation_relevance": "DTO validation tests cover required fields.",
        "migration_concern": "No migration needed.",
        "breaking_risk": "No breaking risk identified.",
        "impact": None,
        **overrides,
    }
    return StagedFileCommitEvidence(
        staged_file=GitStagedFile(path=values["path"], status=values["status"]),
        summary=values["summary"],
        category=values["category"],
        public_contract_impact=values["public_contract_impact"],
        validation_relevance=values["validation_relevance"],
        migration_concern=values["migration_concern"],
        breaking_risk=values["breaking_risk"],
        impact=values["impact"],
    )
