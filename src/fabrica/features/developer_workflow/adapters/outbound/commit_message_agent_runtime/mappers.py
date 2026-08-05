"""Mapping and parsing helpers for commit-message agent-runtime adapters."""

import json
from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import LocalAgentContextBlock, LocalAgentRunCommand
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime.prompts import (
    ANALYZE_STAGED_FILE_PROMPT,
    SYNTHESIZE_COMMIT_MESSAGE_PROMPT,
)
from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageRecommendation,
    SafeGitStagedChangesMetadataValue,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageAnalysisError,
    CommitMessageSynthesisError,
)

REQUIRED_ANALYSIS_FIELDS = (
    "summary",
    "category",
    "public_contract_impact",
    "validation_relevance",
    "migration_concern",
    "breaking_risk",
)


def to_analysis_runtime_command(command: AnalyzeStagedFileForCommitMessageCommand) -> LocalAgentRunCommand:
    """Map one staged-file analysis command to one local agent runtime command."""
    return LocalAgentRunCommand(
        prompt=ANALYZE_STAGED_FILE_PROMPT,
        context=(
            LocalAgentContextBlock(
                text=command.diff.text,
                label=f"Staged file diff: {command.staged_file.path}",
                metadata={
                    "source": "git_staged_file_diff",
                    "path": command.staged_file.path,
                    "status": command.staged_file.status.value,
                    "char_count": len(command.diff.text),
                    **command.diff.metadata,
                },
            ),
        ),
    )


def parse_analysis_output(
    output_text: str,
    command: AnalyzeStagedFileForCommitMessageCommand,
) -> StagedFileCommitEvidence:
    """Parse strict JSON model output into structured staged-file evidence."""
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as err:
        msg = "commit-message analysis returned invalid JSON"
        raise CommitMessageAnalysisError(
            msg,
            metadata={"path": command.staged_file.path, "error_type": type(err).__name__},
        ) from err

    if not isinstance(payload, dict):
        msg = "commit-message analysis returned a non-object JSON value"
        raise CommitMessageAnalysisError(
            msg,
            metadata={"path": command.staged_file.path},
        )

    values = {
        field_name: _required_string(payload, field_name, path=command.staged_file.path)
        for field_name in REQUIRED_ANALYSIS_FIELDS
    }
    impact = _optional_string(payload, "impact", path=command.staged_file.path)
    try:
        return StagedFileCommitEvidence(staged_file=command.staged_file, impact=impact, **values)
    except ValueError as err:
        msg = "commit-message analysis returned invalid evidence fields"
        raise CommitMessageAnalysisError(
            msg,
            metadata={"path": command.staged_file.path, "error_type": type(err).__name__},
        ) from err


def to_synthesis_runtime_command(command: SynthesizeCommitMessageCommand) -> LocalAgentRunCommand:
    """Map final synthesis input to a local agent runtime command."""
    context = [
        LocalAgentContextBlock(
            text=command.evidence_bundle.serialized_text,
            label="Commit-message structured evidence",
            metadata={
                "source": "commit_message_evidence",
                "evidence_count": len(command.evidence_bundle.evidence),
                "char_count": len(command.evidence_bundle.serialized_text),
            },
        ),
    ]
    if command.skill_markdown is not None:
        context.append(
            LocalAgentContextBlock(
                text=command.skill_markdown,
                label=f"Agent Skill: {command.skill_id}",
                metadata={"source": "agent_skill", "skill_id": command.skill_id},
            ),
        )
    return LocalAgentRunCommand(prompt=SYNTHESIZE_COMMIT_MESSAGE_PROMPT, context=tuple(context))


def parse_synthesis_output(output_text: str) -> CommitMessageRecommendation:
    """Parse terminal-friendly labeled synthesis output into a recommendation DTO."""
    sections = _parse_labeled_sections(output_text)
    try:
        return CommitMessageRecommendation(
            summary=sections["Summary"],
            rationale=sections["Rationale"],
            commit_message=sections["Commit message"],
        )
    except KeyError as err:
        msg = "commit-message synthesis output is missing a required label"
        raise CommitMessageSynthesisError(
            msg,
            metadata={"missing_label": str(err).strip("'")},
        ) from err
    except ValueError as err:
        msg = "commit-message synthesis output contains an empty required section"
        raise CommitMessageSynthesisError(
            msg,
            metadata={"error_type": type(err).__name__},
        ) from err


def _required_string(payload: Mapping[str, object], field_name: str, *, path: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        msg = "commit-message analysis returned a missing or non-string field"
        raise CommitMessageAnalysisError(
            msg,
            metadata={"path": path, "field": field_name},
        )
    stripped = value.strip()
    if not stripped:
        msg = "commit-message analysis returned an empty required field"
        raise CommitMessageAnalysisError(
            msg,
            metadata={"path": path, "field": field_name},
        )
    return stripped


def _optional_string(payload: Mapping[str, object], field_name: str, *, path: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = "commit-message analysis returned a non-string optional field"
        raise CommitMessageAnalysisError(
            msg,
            metadata={"path": path, "field": field_name},
        )
    stripped = value.strip()
    if not stripped:
        msg = "commit-message analysis returned an empty optional field"
        raise CommitMessageAnalysisError(
            msg,
            metadata={"path": path, "field": field_name},
        )
    return stripped


def _parse_labeled_sections(output_text: str) -> dict[str, str]:
    labels = ("Summary", "Rationale", "Commit message")
    sections: dict[str, list[str]] = {label: [] for label in labels}
    current_label: str | None = None
    for line in output_text.splitlines():
        stripped_line = line.strip()
        matching_label = next((label for label in labels if stripped_line == f"{label}:"), None)
        if matching_label is not None:
            current_label = matching_label
            continue
        if current_label is not None:
            sections[current_label].append(line)
    return {label: _join_section(lines, label=label) for label, lines in sections.items()}


def _join_section(lines: list[str], *, label: str) -> str:
    text = "\n".join(lines).strip()
    if not text:
        msg = "commit-message synthesis output contains an empty required section"
        raise CommitMessageSynthesisError(
            msg,
            metadata={"label": label},
        )
    return text


def safe_runtime_metadata(status: str, output_text: str | None) -> dict[str, SafeGitStagedChangesMetadataValue]:
    """Return safe diagnostics for failed runtime results without exposing model output."""
    return {"runtime_status": status, "has_output_text": output_text is not None}
