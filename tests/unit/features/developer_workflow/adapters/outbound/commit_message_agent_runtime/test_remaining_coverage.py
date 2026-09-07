"""Focused coverage for commit-message agent-runtime output guards."""

import json

import pytest

from fabrica.features.agent_runtime.application.dtos import RuntimeObservation
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime import analysis, synthesis
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime.analysis_parsing import (
    REQUIRED_ANALYSIS_FIELDS,
    _optional_string,
    parse_analysis_output,
)
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime.metadata import (
    safe_runtime_metadata,
)
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime.synthesis_parsing import (
    parse_synthesis_output,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.parsing import parse_name_status_line
from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    GitStagedDiff,
    GitStagedFile,
    GitStagedFileStatus,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageAnalysisError,
    CommitMessageSynthesisError,
)


def test_analysis_parser_rejects_non_object_and_invalid_required_values() -> None:
    command = _analysis_command()

    for output, match in (
        ("[]", "non-object"),
        (json.dumps(_analysis_payload(summary=" ")), "empty required"),
        (json.dumps(_analysis_payload(impact=42)), "non-string optional"),
        (json.dumps(_analysis_payload(impact=" ")), "empty optional"),
    ):
        with pytest.raises(CommitMessageAnalysisError, match=match):
            parse_analysis_output(output, command)


def test_analysis_runtime_status_mapping_is_fail_closed() -> None:
    configuration = analysis._developer_workflow_status_from_runtime("configuration_error")  # noqa: SLF001
    model = analysis._developer_workflow_status_from_runtime("unexpected")  # noqa: SLF001

    assert configuration.value == "configuration_error"
    assert model.value == "model_error"


def test_analysis_optional_string_rejects_empty_text() -> None:
    with pytest.raises(CommitMessageAnalysisError, match="empty optional"):
        _optional_string({"impact": " "}, "impact", path="src/file.py")

    assert (
        _optional_string({"impact": "Implemented behavior."}, "impact", path="src/file.py") == "Implemented behavior."
    )


def test_synthesis_parser_rejects_empty_sections_and_maps_runtime_statuses() -> None:
    with pytest.raises(CommitMessageSynthesisError, match="empty required"):
        parse_synthesis_output("Summary:\nSummary\nRationale:\nRationale\nCommit message:\n")

    assert synthesis._developer_workflow_status_from_runtime("configuration_error").value == "configuration_error"  # noqa: SLF001
    assert synthesis._developer_workflow_status_from_runtime("failed").value == "model_error"  # noqa: SLF001


def test_synthesis_parser_ignores_text_before_the_first_label() -> None:
    recommendation = parse_synthesis_output(
        "Preamble ignored\nSummary:\nSummary\nRationale:\nRationale\nCommit message:\nfeat: summary\n"
    )

    assert recommendation.commit_message == "feat: summary"


def test_safe_runtime_metadata_omits_observation_fields_when_no_observation_exists() -> None:
    assert safe_runtime_metadata("failed", None) == {"runtime_status": "failed", "has_output_text": False}

    metadata = safe_runtime_metadata(
        "failed",
        "partial output",
        (RuntimeObservation(message="synthetic", metadata={"category": "transport", "secret": "hidden"}),),
    )

    assert metadata == {
        "runtime_status": "failed",
        "has_output_text": True,
        "runtime_category": "transport",
    }


@pytest.mark.parametrize(
    ("line", "match"),
    [
        ("M", "must include status and path"),
        ("R100\told", "must include old and new paths"),
        ("M\ta\tb", "unexpected path fields"),
    ],
)
def test_name_status_parser_rejects_malformed_records(line: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_name_status_line(line)


def _analysis_command() -> AnalyzeStagedFileForCommitMessageCommand:
    return AnalyzeStagedFileForCommitMessageCommand(
        staged_file=GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED),
        diff=GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n"),
    )


def _analysis_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {field: f"{field} value" for field in REQUIRED_ANALYSIS_FIELDS}
    payload.update(overrides)
    return payload
