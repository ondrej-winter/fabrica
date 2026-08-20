"""Offline integration tests for commit-message workflow composition."""

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from fabrica.bootstrap import (
    DEFAULT_COMMIT_MESSAGE_CODEX_MODEL,
    DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT,
    CommitMessageWorkflowOptions,
    create_codex_commit_message_workflow,
    create_commit_message_workflow,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    ModelCostEvidence,
    ModelPricingStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
)
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    DeveloperWorkflowStatus,
    GitStagedChangesFailureCategory,
)

EXPECTED_ONE_FILE_MODEL_CALLS = 2


@dataclass
class FakeRuntime:
    results: list[LocalAgentRunResult]
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    async def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.results.pop(0)


def test_commit_message_workflow_runs_per_file_analysis_then_final_synthesis(tmp_path: Path) -> None:
    runtime = FakeRuntime(
        results=[
            LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text=_analysis_json()),
            LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text=_synthesis_text()),
        ],
    )
    git_repository = _create_repository_with_staged_diff(tmp_path)
    skill_root = _write_commit_message_skill(tmp_path)
    workflow = create_commit_message_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(git_working_directory=git_repository, skill_roots=(skill_root,)),
    )

    result = asyncio.run(workflow.run(skill_id="conventional-commits"))

    assert result.succeeded
    assert result.recommendation == CommitMessageRecommendation(
        summary="Adds an example file.",
        rationale="The structured evidence shows one staged maintenance change.",
        commit_message="chore: add example file",
    )
    assert result.output_text is None
    assert [block.metadata["source"] for call in runtime.calls for block in call.context] == [
        "git_staged_file_diff",
        "commit_message_evidence",
        "agent_skill",
    ]
    assert "diff --git" in runtime.calls[0].context[0].text
    assert "diff --git" not in runtime.calls[1].context[0].text


def test_commit_message_workflow_propagates_model_evidence_from_all_runtime_calls(tmp_path: Path) -> None:
    analysis_usage = ModelUsageEvidence(
        provider="codex",
        status=ModelUsageCollectionStatus.COLLECTED,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.EXTRACTED,
        model="gpt-5.3-codex-spark",
        tokens=ModelTokenUsageEvidence(input_tokens=10, output_tokens=5, total_tokens=15),
    )
    synthesis_usage = ModelUsageEvidence(
        provider="codex",
        status=ModelUsageCollectionStatus.COLLECTED,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.EXTRACTED,
        model="gpt-5.3-codex-spark",
        tokens=ModelTokenUsageEvidence(input_tokens=20, output_tokens=8, total_tokens=28),
    )
    synthesis_cost = ModelCostEvidence(
        pricing_status=ModelPricingStatus.UNKNOWN,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.UNKNOWN,
    )
    runtime = FakeRuntime(
        results=[
            LocalAgentRunResult(
                status=LocalAgentRunStatus.SUCCESS,
                output_text=_analysis_json(),
                usage_evidence=(analysis_usage,),
            ),
            LocalAgentRunResult(
                status=LocalAgentRunStatus.SUCCESS,
                output_text=_synthesis_text(),
                usage_evidence=(synthesis_usage,),
                cost_evidence=(synthesis_cost,),
            ),
        ],
    )
    git_repository = _create_repository_with_staged_diff(tmp_path)
    skill_root = _write_commit_message_skill(tmp_path)
    workflow = create_commit_message_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(git_working_directory=git_repository, skill_roots=(skill_root,)),
    )

    result = asyncio.run(workflow.run(skill_id="conventional-commits"))

    assert result.succeeded
    assert result.usage_evidence == (analysis_usage, synthesis_usage)
    assert result.cost_evidence == (synthesis_cost,)


def test_commit_message_workflow_stops_before_runtime_when_staged_discovery_fails(tmp_path: Path) -> None:
    runtime = FakeRuntime(results=[])
    git_repository = tmp_path / "repo"
    git_repository.mkdir()
    _run_git(("git", "init"), cwd=git_repository)
    workflow = create_commit_message_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(
            git_working_directory=git_repository,
        ),
    )

    result = asyncio.run(workflow.run())

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.observations[0].metadata["category"] == GitStagedChangesFailureCategory.NO_STAGED_CHANGES
    assert runtime.calls == []


def test_codex_commit_message_workflow_uses_spark_low_defaults_with_mock_transport(tmp_path: Path) -> None:
    auth_file_path = _write_synthetic_auth_file(tmp_path)
    skill_root = _write_commit_message_skill(tmp_path)
    git_repository = _create_repository_with_staged_diff(tmp_path)
    observed_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_payloads.append(json.loads(request.content.decode("utf-8")))
        output_text = _analysis_json() if len(observed_payloads) == 1 else _synthesis_text()
        return httpx.Response(200, json={"output_text": output_text})

    workflow = create_codex_commit_message_workflow(
        CommitMessageWorkflowOptions(
            codex_auth_file_path=auth_file_path,
            codex_http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            git_working_directory=git_repository,
            skill_roots=(skill_root,),
        ),
    )

    result = asyncio.run(workflow.run())

    assert result.succeeded
    assert len(observed_payloads) == EXPECTED_ONE_FILE_MODEL_CALLS
    assert observed_payloads[0]["model"] == DEFAULT_COMMIT_MESSAGE_CODEX_MODEL
    assert observed_payloads[0]["reasoning"] == {"effort": DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT}
    assert observed_payloads[1]["model"] == DEFAULT_COMMIT_MESSAGE_CODEX_MODEL
    assert observed_payloads[1]["reasoning"] == {"effort": DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT}


def test_codex_commit_message_workflow_allows_model_and_effort_overrides(tmp_path: Path) -> None:
    auth_file_path = _write_synthetic_auth_file(tmp_path)
    skill_root = _write_commit_message_skill(tmp_path)
    git_repository = _create_repository_with_staged_diff(tmp_path)
    observed_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_payloads.append(json.loads(request.content.decode("utf-8")))
        output_text = _analysis_json() if len(observed_payloads) == 1 else _synthesis_text()
        return httpx.Response(200, json={"output_text": output_text})

    workflow = create_codex_commit_message_workflow(
        CommitMessageWorkflowOptions(
            codex_model="gpt-5.6-sol",
            codex_reasoning_effort="medium",
            codex_auth_file_path=auth_file_path,
            codex_http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            git_working_directory=git_repository,
            skill_roots=(skill_root,),
        ),
    )

    result = asyncio.run(workflow.run())

    assert result.succeeded
    assert len(observed_payloads) == EXPECTED_ONE_FILE_MODEL_CALLS
    assert observed_payloads[0]["model"] == "gpt-5.6-sol"
    assert observed_payloads[0]["reasoning"] == {"effort": "medium"}
    assert observed_payloads[1]["model"] == "gpt-5.6-sol"
    assert observed_payloads[1]["reasoning"] == {"effort": "medium"}


def _analysis_json() -> str:
    return json.dumps(
        {
            "summary": "Adds an example file.",
            "category": "maintenance",
            "public_contract_impact": "No public contract impact identified.",
            "validation_relevance": "No validation relevance identified.",
            "migration_concern": "No migration concern identified.",
            "breaking_risk": "No breaking risk identified.",
        }
    )


def _synthesis_text() -> str:
    return (
        "Summary:\nAdds an example file.\n\n"
        "Rationale:\nThe structured evidence shows one staged maintenance change.\n\n"
        "Commit message:\nchore: add example file"
    )


def _write_synthetic_auth_file(tmp_path: Path) -> Path:
    auth_file_path = tmp_path / "auth.json"
    auth_file_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "synthetic-access-token",
                    "account_id": "synthetic-account",
                },
            }
        ),
        encoding="utf-8",
    )
    return auth_file_path


def _write_commit_message_skill(tmp_path: Path) -> Path:
    skill_root = tmp_path / "skills"
    skill_directory = skill_root / "conventional-commits"
    skill_directory.mkdir(parents=True)
    (skill_directory / "SKILL.md").write_text(
        "# Conventional Commits\nUse concise commit messages.\n", encoding="utf-8"
    )
    return skill_root


def _create_repository_with_staged_diff(tmp_path: Path) -> Path:
    git_repository = tmp_path / "repo"
    git_repository.mkdir()
    _run_git(("git", "init"), cwd=git_repository)
    (git_repository / "example.txt").write_text("example\n", encoding="utf-8")
    _run_git(("git", "add", "example.txt"), cwd=git_repository)
    return git_repository


def _run_git(argv: tuple[str, ...], *, cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, capture_output=True)  # noqa: S603
