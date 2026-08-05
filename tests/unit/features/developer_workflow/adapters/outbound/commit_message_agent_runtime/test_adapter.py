"""Tests for commit-message agent-runtime outbound adapters."""

import json
from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
)
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime import (
    AgentRuntimeCommitMessageSynthesizer,
    AgentRuntimeStagedFileCommitMessageAnalyzer,
)
from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageEvidenceBundle,
    GitStagedDiff,
    GitStagedFile,
    GitStagedFileStatus,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageAnalysisError,
    CommitMessageSynthesisError,
)


@dataclass
class FakeRuntime:
    result: LocalAgentRunResult
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.result


def test_analyzer_sends_one_file_diff_and_parses_strict_json_evidence() -> None:
    runtime = FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text=_analysis_json()))
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)

    evidence = AgentRuntimeStagedFileCommitMessageAnalyzer(runtime).analyze(
        AnalyzeStagedFileForCommitMessageCommand(
            staged_file=staged_file,
            diff=GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+change\n"),
        ),
    )

    assert evidence == StagedFileCommitEvidence(
        staged_file=staged_file,
        summary="Adds adapter mapping.",
        category="architecture",
        public_contract_impact="No public contract impact identified.",
        validation_relevance="Adapter unit tests cover parser behavior.",
        migration_concern="No migration concern identified.",
        breaking_risk="No breaking risk identified.",
    )
    assert len(runtime.calls) == 1
    assert "Do not write, recommend, draft, or synthesize a final commit message." in runtime.calls[0].prompt
    assert [block.metadata["source"] for block in runtime.calls[0].context] == ["git_staged_file_diff"]
    assert runtime.calls[0].context[0].text == "diff --git a/src/file.py b/src/file.py\n+change\n"


@pytest.mark.parametrize(
    ("output_text", "match", "overrides"),
    [
        ("not json", "invalid JSON", None),
        ('{"summary": "Adds adapter mapping."}', "missing or non-string field", None),
        (None, "empty required field", {"summary": " "}),
        (None, "empty optional field", {"impact": " "}),
    ],
)
def test_analyzer_rejects_invalid_structured_output_safely(
    output_text: str | None,
    match: str,
    overrides: dict[str, str] | None,
) -> None:
    invalid_output = output_text or _analysis_json(**(overrides or {}))
    runtime = FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text=invalid_output))
    command = AnalyzeStagedFileForCommitMessageCommand(
        staged_file=GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED),
        diff=GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+change\n"),
    )

    with pytest.raises(CommitMessageAnalysisError, match=match) as error_info:
        AgentRuntimeStagedFileCommitMessageAnalyzer(runtime).analyze(command)

    assert error_info.value.metadata["path"] == "src/file.py"


def test_analyzer_maps_runtime_failure_without_exposing_output_text() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.MODEL_ERROR, output_text="raw model failure details"),
    )
    command = AnalyzeStagedFileForCommitMessageCommand(
        staged_file=GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED),
        diff=GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+change\n"),
    )

    with pytest.raises(CommitMessageAnalysisError) as error_info:
        AgentRuntimeStagedFileCommitMessageAnalyzer(runtime).analyze(command)

    assert error_info.value.metadata == {
        "path": "src/file.py",
        "runtime_status": "model_error",
        "has_output_text": True,
    }


def test_synthesizer_sends_structured_evidence_and_skill_context_then_parses_labels() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(
            status=LocalAgentRunStatus.SUCCESS,
            output_text=(
                "Summary:\nAdds agent-runtime commit-message adapters.\n\n"
                "Rationale:\nThe structured evidence shows a developer-workflow adapter slice.\n\n"
                "Commit message:\nfeat(developer-workflow): add commit message runtime adapters"
            ),
        ),
    )
    bundle = CommitMessageEvidenceBundle(evidence=(_evidence(),))

    recommendation = AgentRuntimeCommitMessageSynthesizer(runtime).synthesize(
        SynthesizeCommitMessageCommand(evidence_bundle=bundle, skill_markdown="# Conventional Commits\nUse feat.\n"),
    )

    assert recommendation.commit_message == "feat(developer-workflow): add commit message runtime adapters"
    assert len(runtime.calls) == 1
    assert "Use exactly these labels:" in runtime.calls[0].prompt
    assert [block.metadata["source"] for block in runtime.calls[0].context] == [
        "commit_message_evidence",
        "agent_skill",
    ]
    assert runtime.calls[0].context[0].text == bundle.serialized_text
    assert "diff --git" not in runtime.calls[0].context[0].text


def test_synthesizer_rejects_missing_required_labels() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="Summary:\nOnly summary")
    )

    with pytest.raises(CommitMessageSynthesisError, match="empty required section"):
        AgentRuntimeCommitMessageSynthesizer(runtime).synthesize(
            SynthesizeCommitMessageCommand(evidence_bundle=CommitMessageEvidenceBundle(evidence=(_evidence(),))),
        )


def test_synthesizer_maps_runtime_failure_without_exposing_output_text() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.MODEL_ERROR, output_text="raw model failure details"),
    )

    with pytest.raises(CommitMessageSynthesisError) as error_info:
        AgentRuntimeCommitMessageSynthesizer(runtime).synthesize(
            SynthesizeCommitMessageCommand(evidence_bundle=CommitMessageEvidenceBundle(evidence=(_evidence(),))),
        )

    assert error_info.value.metadata == {"runtime_status": "model_error", "has_output_text": True}


def _analysis_json(**overrides: str) -> str:
    payload = {
        "summary": "Adds adapter mapping.",
        "category": "architecture",
        "public_contract_impact": "No public contract impact identified.",
        "validation_relevance": "Adapter unit tests cover parser behavior.",
        "migration_concern": "No migration concern identified.",
        "breaking_risk": "No breaking risk identified.",
        **overrides,
    }
    return json.dumps(payload)


def _evidence() -> StagedFileCommitEvidence:
    return StagedFileCommitEvidence(
        staged_file=GitStagedFile(path="src/adapter.py", status=GitStagedFileStatus.ADDED),
        summary="Adds runtime adapter.",
        category="architecture",
        public_contract_impact="No public contract impact identified.",
        validation_relevance="Unit tests cover adapter behavior.",
        migration_concern="No migration concern identified.",
        breaking_risk="No breaking risk identified.",
    )
