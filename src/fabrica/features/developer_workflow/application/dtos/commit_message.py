"""Application DTOs for evidence-first commit-message generation."""

from dataclasses import dataclass, field

from fabrica.features.developer_workflow.application.dtos.git_staged_changes import (
    GitStagedDiff,
    GitStagedFile,
)

DEFAULT_COMMIT_MESSAGE_SKILL_ID = "conventional-commits"
DEFAULT_MAX_COMMIT_MESSAGE_STAGED_FILES = 50
DEFAULT_MAX_COMMIT_MESSAGE_EVIDENCE_CHARS = 50_000


@dataclass(frozen=True, slots=True)
class AnalyzeStagedFileForCommitMessageCommand:
    """Command to analyze one staged file diff for commit-message evidence."""

    staged_file: GitStagedFile
    diff: GitStagedDiff


@dataclass(frozen=True, slots=True)
class StagedFileCommitEvidence:
    """Structured evidence extracted from one staged file for commit synthesis."""

    staged_file: GitStagedFile
    summary: str
    category: str
    public_contract_impact: str
    validation_relevance: str
    migration_concern: str
    breaking_risk: str
    impact: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", _validate_required_text(self.summary, field_name="summary"))
        object.__setattr__(self, "category", _validate_required_text(self.category, field_name="category"))
        object.__setattr__(
            self,
            "public_contract_impact",
            _validate_required_text(self.public_contract_impact, field_name="public_contract_impact"),
        )
        object.__setattr__(
            self,
            "validation_relevance",
            _validate_required_text(self.validation_relevance, field_name="validation_relevance"),
        )
        object.__setattr__(
            self,
            "migration_concern",
            _validate_required_text(self.migration_concern, field_name="migration_concern"),
        )
        object.__setattr__(
            self,
            "breaking_risk",
            _validate_required_text(self.breaking_risk, field_name="breaking_risk"),
        )
        if self.impact is not None:
            object.__setattr__(self, "impact", _validate_optional_text(self.impact, field_name="impact"))


@dataclass(frozen=True, slots=True)
class CommitMessageEvidenceBundle:
    """Ordered evidence bundle passed to final commit-message synthesis."""

    evidence: tuple[StagedFileCommitEvidence, ...]
    max_serialized_chars: int = DEFAULT_MAX_COMMIT_MESSAGE_EVIDENCE_CHARS
    serialized_text: str = field(init=False)

    def __post_init__(self) -> None:
        evidence = tuple(self.evidence)
        if not evidence:
            msg = "commit-message evidence bundle must not be empty"
            raise ValueError(msg)
        if self.max_serialized_chars < 1:
            msg = "max_serialized_chars must be at least 1"
            raise ValueError(msg)
        serialized_text = _serialize_evidence(evidence)
        if len(serialized_text) > self.max_serialized_chars:
            msg = "commit-message evidence bundle exceeds the configured serialized evidence bound"
            raise ValueError(msg)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "serialized_text", serialized_text)


@dataclass(frozen=True, slots=True)
class SynthesizeCommitMessageCommand:
    """Command to synthesize a final recommendation from structured evidence."""

    evidence_bundle: CommitMessageEvidenceBundle
    skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    skill_markdown: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_id", _validate_required_text(self.skill_id, field_name="skill_id"))
        if self.skill_markdown is not None:
            object.__setattr__(
                self,
                "skill_markdown",
                _validate_optional_text(self.skill_markdown, field_name="skill_markdown"),
            )


@dataclass(frozen=True, slots=True)
class CommitMessageRecommendation:
    """Final Conventional Commit recommendation for terminal output."""

    summary: str
    rationale: str
    commit_message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", _validate_required_text(self.summary, field_name="summary"))
        object.__setattr__(self, "rationale", _validate_required_text(self.rationale, field_name="rationale"))
        object.__setattr__(
            self,
            "commit_message",
            _validate_required_text(self.commit_message, field_name="commit_message"),
        )


@dataclass(frozen=True, slots=True)
class GenerateCommitMessageResult:
    """Result of the full evidence-first commit-message workflow."""

    recommendation: CommitMessageRecommendation
    evidence_bundle: CommitMessageEvidenceBundle


def _serialize_evidence(evidence: tuple[StagedFileCommitEvidence, ...]) -> str:
    lines: list[str] = []
    for index, item in enumerate(evidence, start=1):
        lines.extend(
            (
                f"File {index}: {item.staged_file.path}",
                f"Status: {item.staged_file.status.value}",
                f"Category: {item.category}",
                f"Summary: {item.summary}",
                f"Public contract impact: {item.public_contract_impact}",
                f"Validation relevance: {item.validation_relevance}",
                f"Migration concern: {item.migration_concern}",
                f"Breaking risk: {item.breaking_risk}",
            )
        )
        if item.impact is not None:
            lines.append(f"Impact: {item.impact}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _validate_required_text(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    return stripped


def _validate_optional_text(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        msg = f"{field_name} must not be empty when provided"
        raise ValueError(msg)
    return stripped
