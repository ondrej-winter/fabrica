"""Parsing for staged-file commit-message evidence model output."""

import json
from collections.abc import Mapping

from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    StagedFileCommitEvidence,
)
from fabrica.features.developer_workflow.application.ports import CommitMessageAnalysisError

REQUIRED_ANALYSIS_FIELDS = (
    "summary",
    "category",
    "public_contract_impact",
    "validation_relevance",
    "migration_concern",
    "breaking_risk",
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
