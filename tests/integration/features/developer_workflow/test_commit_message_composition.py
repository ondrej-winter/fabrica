"""Offline integration tests for commit-message workflow composition."""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from fabrica.bootstrap import (
    DEFAULT_COMMIT_MESSAGE_CODEX_MODEL,
    DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT,
    CommitMessageWorkflow,
    CommitMessageWorkflowOptions,
    create_codex_commit_message_workflow,
)
from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillContext,
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    SelectedSkill,
)
from fabrica.features.agent_runtime.application.use_cases import LoadSkillContext
from fabrica.features.developer_workflow.application.dtos import (
    GitStagedChangesFailureCategory,
    GitStagedDiff,
)
from fabrica.features.developer_workflow.application.ports import GitStagedChangesLoadError
from fabrica.features.developer_workflow.application.use_cases import PrepareCommitMessageRun


@dataclass
class FakeStagedChangesLoader:
    diff: GitStagedDiff | None = None
    error: GitStagedChangesLoadError | None = None

    def load(self) -> GitStagedDiff:
        return self.load_diff()

    def load_diff(self) -> GitStagedDiff:
        if self.error is not None:
            raise self.error
        return self.diff or GitStagedDiff(text="diff --git a/file.py b/file.py\n")


@dataclass
class FakeSkillContextLoader:
    def load(self, selection: SelectedSkill) -> LoadedSkillContext:
        return LoadedSkillContext(skill_id=selection.skill_id, markdown="# Conventional Commits\n")


@dataclass
class FakeRuntime:
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="ok")


def test_commit_message_workflow_runs_runtime_after_preparation() -> None:
    runtime = FakeRuntime()
    workflow = CommitMessageWorkflow(
        preparer=PrepareCommitMessageRun(FakeStagedChangesLoader(), LoadSkillContext(FakeSkillContextLoader())),
        runtime=runtime,
    )

    result = workflow.run(skill_id="conventional-commits")

    assert result.succeeded
    assert runtime.calls
    assert [block.metadata["source"] for block in runtime.calls[0].context] == ["git_staged_diff", "agent_skill"]


def test_commit_message_workflow_stops_before_runtime_when_staged_diff_fails() -> None:
    runtime = FakeRuntime()
    workflow = CommitMessageWorkflow(
        preparer=PrepareCommitMessageRun(
            FakeStagedChangesLoader(
                error=GitStagedChangesLoadError(
                    "no staged git changes were found",
                    category=GitStagedChangesFailureCategory.NO_STAGED_CHANGES,
                ),
            ),
            LoadSkillContext(FakeSkillContextLoader()),
        ),
        runtime=runtime,
    )

    result = workflow.run()

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
    assert runtime.calls == []


def test_codex_commit_message_workflow_uses_spark_low_defaults_with_mock_transport(tmp_path: Path) -> None:
    auth_file_path = _write_synthetic_auth_file(tmp_path)
    skill_root = _write_commit_message_skill(tmp_path)
    git_repository = _create_repository_with_staged_diff(tmp_path)
    observed_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"output_text": "feat: add example"})

    workflow = create_codex_commit_message_workflow(
        CommitMessageWorkflowOptions(
            codex_auth_file_path=auth_file_path,
            codex_http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            git_working_directory=git_repository,
            skill_roots=(skill_root,),
        ),
    )

    result = workflow.run()

    assert result.succeeded
    assert observed_payloads[0]["model"] == DEFAULT_COMMIT_MESSAGE_CODEX_MODEL
    assert observed_payloads[0]["reasoning"] == {"effort": DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT}


def test_codex_commit_message_workflow_allows_model_and_effort_overrides(tmp_path: Path) -> None:
    auth_file_path = _write_synthetic_auth_file(tmp_path)
    skill_root = _write_commit_message_skill(tmp_path)
    git_repository = _create_repository_with_staged_diff(tmp_path)
    observed_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"output_text": "feat: add example"})

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

    result = workflow.run()

    assert result.succeeded
    assert observed_payloads[0]["model"] == "gpt-5.6-sol"
    assert observed_payloads[0]["reasoning"] == {"effort": "medium"}


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
