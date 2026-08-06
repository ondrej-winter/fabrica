"""Tests for the approved git commit subprocess adapter."""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_commit_subprocess import (
    GitCommitCommandResult,
    GitCommitSubprocessCreator,
)
from fabrica.features.developer_workflow.application.dtos import CreateGitCommitCommand, GitCommitResult
from fabrica.features.developer_workflow.application.ports import GitCommitError

GIT_COMMIT_FILE_ARGC = 5
TEST_TIMEOUT_SECONDS = 2.5


@dataclass
class FakeGitCommitRunner:
    result: GitCommitCommandResult | None = None
    results: list[GitCommitCommandResult] = field(default_factory=list)
    error: BaseException | None = None
    errors_by_call: dict[int, BaseException] = field(default_factory=dict)
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)
    observed_message_files: list[tuple[Path, str]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        if len(argv) >= GIT_COMMIT_FILE_ARGC and tuple(argv[:4]) == ("git", "--no-pager", "commit", "--file"):
            message_file_path = Path(argv[4])
            self.observed_message_files.append((message_file_path, message_file_path.read_text(encoding="utf-8")))
        if len(self.calls) in self.errors_by_call:
            raise self.errors_by_call[len(self.calls)]
        if self.error is not None:
            raise self.error
        if self.results:
            return self.results.pop(0)
        if self.result is not None:
            return self.result
        return GitCommitCommandResult(returncode=0, stdout="abc1234\n")


def test_adapter_invokes_git_commit_file_command_with_exact_message() -> None:
    runner = FakeGitCommitRunner(
        results=[GitCommitCommandResult(returncode=0), GitCommitCommandResult(returncode=0, stdout="abc1234\n")]
    )
    message = "feat: add commit flow\n\nBody.\n\nRefs: #123\n"

    result = GitCommitSubprocessCreator(
        working_directory=Path("repo"),
        timeout_seconds=TEST_TIMEOUT_SECONDS,
        runner=runner,
    ).create_commit(CreateGitCommitCommand(message=message))

    assert result == GitCommitResult(short_hash="abc1234")
    commit_argv, cwd, timeout_seconds = runner.calls[0]
    assert commit_argv[:4] == ("git", "--no-pager", "commit", "--file")
    assert cwd == Path("repo")
    assert timeout_seconds == TEST_TIMEOUT_SECONDS
    assert runner.calls[1] == (
        ("git", "--no-pager", "rev-parse", "--short", "HEAD"),
        Path("repo"),
        TEST_TIMEOUT_SECONDS,
    )
    assert runner.observed_message_files[0][1] == message


def test_adapter_cleans_up_temporary_message_file_after_success() -> None:
    runner = FakeGitCommitRunner(
        results=[GitCommitCommandResult(returncode=0), GitCommitCommandResult(returncode=0, stdout="abc1234\n")]
    )

    GitCommitSubprocessCreator(runner=runner).create_commit(CreateGitCommitCommand(message="feat: add commit flow"))

    assert not runner.observed_message_files[0][0].exists()


def test_adapter_cleans_up_temporary_message_file_after_git_failure() -> None:
    runner = FakeGitCommitRunner(result=GitCommitCommandResult(returncode=1, stderr="fatal: hook declined"))

    with pytest.raises(GitCommitError):
        GitCommitSubprocessCreator(runner=runner).create_commit(CreateGitCommitCommand(message="feat: add commit flow"))

    assert not runner.observed_message_files[0][0].exists()


@pytest.mark.parametrize(
    ("result", "category", "message"),
    [
        (
            GitCommitCommandResult(returncode=128, stderr="fatal: not a git repository"),
            "not_a_repository",
            "repository",
        ),
        (
            GitCommitCommandResult(returncode=1, stderr="nothing to commit, working tree clean"),
            "no_staged_changes",
            "staged",
        ),
        (GitCommitCommandResult(returncode=1, stderr="fatal: hook declined"), "git_failed", "git commit failed"),
    ],
)
def test_adapter_maps_non_zero_commit_failures(
    result: GitCommitCommandResult,
    category: str,
    message: str,
) -> None:
    with pytest.raises(GitCommitError, match=message) as exc_info:
        GitCommitSubprocessCreator(runner=FakeGitCommitRunner(result=result)).create_commit(
            CreateGitCommitCommand(message="feat: add commit flow"),
        )

    assert exc_info.value.metadata["category"] == category
    assert exc_info.value.metadata["returncode"] == result.returncode
    assert "hook declined" not in str(exc_info.value.metadata)


@pytest.mark.parametrize(
    ("error", "category", "message"),
    [
        (FileNotFoundError("git"), "git_unavailable", "unavailable"),
        (subprocess.TimeoutExpired(cmd=["git", "commit"], timeout=1.0), "timed_out", "timed out"),
        (OSError("boom"), "git_failed", "failed to start"),
    ],
)
def test_adapter_maps_subprocess_failures(error: BaseException, category: str, message: str) -> None:
    runner = FakeGitCommitRunner(error=error)

    with pytest.raises(GitCommitError, match=message) as exc_info:
        GitCommitSubprocessCreator(runner=runner).create_commit(CreateGitCommitCommand(message="feat: add commit flow"))

    assert exc_info.value.metadata["category"] == category
    assert not runner.observed_message_files[0][0].exists()


def test_adapter_maps_decode_failure_without_raw_output_diagnostics() -> None:
    runner = FakeGitCommitRunner(result=GitCommitCommandResult(returncode=1, stderr=b"\xff"))

    with pytest.raises(GitCommitError, match="decoded") as exc_info:
        GitCommitSubprocessCreator(runner=runner).create_commit(CreateGitCommitCommand(message="feat: add commit flow"))

    assert exc_info.value.metadata["category"] == "decode_error"
    assert "\xff" not in str(exc_info.value.metadata)


def test_adapter_returns_success_without_hash_when_hash_lookup_fails() -> None:
    runner = FakeGitCommitRunner(
        results=[
            GitCommitCommandResult(returncode=0),
            GitCommitCommandResult(returncode=128, stderr="fatal: cannot resolve HEAD"),
        ],
    )

    result = GitCommitSubprocessCreator(runner=runner).create_commit(
        CreateGitCommitCommand(message="feat: add commit flow")
    )

    assert result == GitCommitResult(short_hash=None)


def test_adapter_returns_success_without_hash_when_hash_lookup_start_fails() -> None:
    runner = FakeGitCommitRunner(
        results=[GitCommitCommandResult(returncode=0)],
        errors_by_call={2: subprocess.TimeoutExpired(cmd=["git", "rev-parse"], timeout=1.0)},
    )

    result = GitCommitSubprocessCreator(runner=runner).create_commit(
        CreateGitCommitCommand(message="feat: add commit flow")
    )

    assert result == GitCommitResult(short_hash=None)


def test_adapter_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="positive"):
        GitCommitSubprocessCreator(timeout_seconds=0)
