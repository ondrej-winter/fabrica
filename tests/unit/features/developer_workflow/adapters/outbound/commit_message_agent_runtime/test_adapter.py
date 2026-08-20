"""Tests for commit-message agent-runtime outbound adapters."""

import asyncio
import json
from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
    SelectedSkill,
)
from fabrica.features.agent_runtime.application.ports import SkillContextLoadError
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime import (
    AgentRuntimeCommitMessageSynthesizer,
    AgentRuntimeStagedFileCommitMessageAnalyzer,
    SkillContextCommitMessageSynthesizer,
)
from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    GitStagedDiff,
    GitStagedFile,
    GitStagedFileStatus,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageAnalysisError,
    CommitMessageSkillContextLoadError,
    CommitMessageSynthesisError,
)


@dataclass
class FakeRuntime:
    result: LocalAgentRunResult
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    async def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.result


@dataclass
class RecordingSynthesizer:
    recommendation: CommitMessageRecommendation
    calls: list[SynthesizeCommitMessageCommand] = field(default_factory=list)

    async def synthesize(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        self.calls.append(command)
        return self.recommendation


@dataclass
class FakeSkillContextLoader:
    contexts: tuple[LocalAgentContextBlock, ...] = ()
    error: SkillContextLoadError | None = None
    calls: list[tuple[SelectedSkill, ...]] = field(default_factory=list)

    def load(self, selections: tuple[SelectedSkill, ...]) -> tuple[LocalAgentContextBlock, ...]:
        self.calls.append(selections)
        if self.error is not None:
            raise self.error
        return self.contexts


def test_analyzer_sends_one_file_diff_and_parses_strict_json_evidence() -> None:
    runtime = FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text=_analysis_json()))
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)

    evidence = asyncio.run(
        AgentRuntimeStagedFileCommitMessageAnalyzer(runtime).analyze(
            AnalyzeStagedFileForCommitMessageCommand(
                staged_file=staged_file,
                diff=GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+change\n"),
            ),
        )
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
        asyncio.run(AgentRuntimeStagedFileCommitMessageAnalyzer(runtime).analyze(command))

    assert error_info.value.metadata["path"] == "src/file.py"


def test_analyzer_maps_runtime_failure_without_exposing_output_text() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(
            status=LocalAgentRunStatus.MODEL_ERROR,
            output_text="raw model failure details",
            observations=(
                RuntimeObservation(
                    message="Codex backend request was rate limited",
                    metadata={
                        "transport_status": "rate_limited",
                        "http_status": 429,
                        "category": "rate_limit",
                        "error_type": "usage_limit_reached",
                        "response_shape": "error",
                        "authorization": "Bearer synthetic-token",
                    },
                ),
            ),
        ),
    )
    command = AnalyzeStagedFileForCommitMessageCommand(
        staged_file=GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED),
        diff=GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+change\n"),
    )

    with pytest.raises(CommitMessageAnalysisError) as error_info:
        asyncio.run(AgentRuntimeStagedFileCommitMessageAnalyzer(runtime).analyze(command))

    assert error_info.value.metadata == {
        "path": "src/file.py",
        "runtime_status": "model_error",
        "has_output_text": True,
        "runtime_transport_status": "rate_limited",
        "runtime_http_status": 429,
        "runtime_category": "rate_limit",
        "runtime_error_type": "usage_limit_reached",
        "runtime_response_shape": "error",
    }
    assert "synthetic-token" not in str(error_info.value.metadata)


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

    recommendation = asyncio.run(
        AgentRuntimeCommitMessageSynthesizer(runtime).synthesize(
            SynthesizeCommitMessageCommand(
                evidence_bundle=bundle, skill_markdown="# Conventional Commits\nUse feat.\n"
            ),
        )
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
        asyncio.run(
            AgentRuntimeCommitMessageSynthesizer(runtime).synthesize(
                SynthesizeCommitMessageCommand(evidence_bundle=CommitMessageEvidenceBundle(evidence=(_evidence(),))),
            )
        )


def test_synthesizer_maps_runtime_failure_without_exposing_output_text() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(
            status=LocalAgentRunStatus.MODEL_ERROR,
            output_text="raw model failure details",
            observations=(
                RuntimeObservation(
                    message="Codex backend request was rate limited",
                    metadata={
                        "transport_status": "rate_limited",
                        "http_status": 429,
                        "category": "rate_limit",
                        "error_type": "usage_limit_reached",
                        "response_shape": "error",
                        "authorization": "Bearer synthetic-token",
                    },
                ),
            ),
        ),
    )

    with pytest.raises(CommitMessageSynthesisError) as error_info:
        asyncio.run(
            AgentRuntimeCommitMessageSynthesizer(runtime).synthesize(
                SynthesizeCommitMessageCommand(evidence_bundle=CommitMessageEvidenceBundle(evidence=(_evidence(),))),
            )
        )

    assert error_info.value.metadata == {
        "runtime_status": "model_error",
        "has_output_text": True,
        "runtime_transport_status": "rate_limited",
        "runtime_http_status": 429,
        "runtime_category": "rate_limit",
        "runtime_error_type": "usage_limit_reached",
        "runtime_response_shape": "error",
    }
    assert "synthetic-token" not in str(error_info.value.metadata)


def test_skill_context_synthesizer_loads_selected_skill_markdown_before_synthesis() -> None:
    recommendation = CommitMessageRecommendation(
        summary="Adds context.",
        rationale="The selected skill markdown is loaded before synthesis.",
        commit_message="feat: load skill context",
    )
    synthesizer = RecordingSynthesizer(recommendation=recommendation)
    loader = FakeSkillContextLoader(
        contexts=(
            LocalAgentContextBlock(
                text="# Conventional Commits\nUse feat.\n",
                metadata={"skill_id": "team-style"},
            ),
        )
    )
    bundle = CommitMessageEvidenceBundle(evidence=(_evidence(),))

    result = asyncio.run(
        SkillContextCommitMessageSynthesizer(
            synthesizer=synthesizer,
            skill_context_loader=loader,
        ).synthesize(SynthesizeCommitMessageCommand(evidence_bundle=bundle, skill_id="team-style"))
    )

    assert result is recommendation
    assert loader.calls == [(SelectedSkill(skill_id="team-style"),)]
    assert synthesizer.calls == [
        SynthesizeCommitMessageCommand(
            evidence_bundle=bundle,
            skill_id="team-style",
            skill_markdown="# Conventional Commits\nUse feat.\n",
        )
    ]


def test_skill_context_synthesizer_translates_agent_runtime_context_errors() -> None:
    loader = FakeSkillContextLoader(
        error=SkillContextLoadError(
            "selected skill was not found",
            skill_id="missing-skill",
            category="skill_not_found",
            metadata={"skill_id": "missing-skill"},
        )
    )
    synthesizer = RecordingSynthesizer(
        recommendation=CommitMessageRecommendation(
            summary="Unused.",
            rationale="Unused.",
            commit_message="chore: unused",
        )
    )

    with pytest.raises(CommitMessageSkillContextLoadError) as error_info:
        asyncio.run(
            SkillContextCommitMessageSynthesizer(
                synthesizer=synthesizer,
                skill_context_loader=loader,
            ).synthesize(
                SynthesizeCommitMessageCommand(evidence_bundle=CommitMessageEvidenceBundle(evidence=(_evidence(),)))
            )
        )

    assert str(error_info.value) == "selected skill was not found"
    assert error_info.value.category == "skill_not_found"
    assert error_info.value.metadata == {"skill_id": "missing-skill"}
    assert synthesizer.calls == []


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
