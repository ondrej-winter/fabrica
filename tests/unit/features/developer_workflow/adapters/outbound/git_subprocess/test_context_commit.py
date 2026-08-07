"""Tests for read-only git commit context subprocess behavior."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess import (
    GitCommandResult,
    GitContextSubprocessLoader,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitContextFailureCategory,
    GitContextLogCount,
)
from fabrica.features.developer_workflow.application.ports import GitContextLoadError


@dataclass
class FakeGitRunner:
    """Deterministic fake for commit context git subprocess calls."""

    results: list[GitCommandResult]
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        return self.results.pop(0)


def test_commit_log_loads_default_bounded_recent_commit_metadata() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(
                returncode=0,
                stdout="abcdef123456\x1fabcdef1\x1fAdd context\x1f2026-08-07T18:00:00+00:00\x1fHEAD -> main\x1e",
            )
        ]
    )

    log = GitContextSubprocessLoader(working_directory=Path("repo"), runner=runner).list_commits()

    assert [(commit.short_hash, commit.subject, commit.refs) for commit in log.commits] == [
        ("abcdef1", "Add context", ("HEAD -> main",)),
    ]
    assert runner.calls == [
        (
            (
                "git",
                "--no-pager",
                "log",
                "--max-count=20",
                "--format=%H%x1f%h%x1f%s%x1f%aI%x1f%D%x1e",
                "HEAD",
            ),
            Path("repo"),
            10.0,
        )
    ]


def test_commit_log_uses_explicit_bounded_count() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(
                returncode=0,
                stdout="abcdef123456\x1fabcdef1\x1fAdd context\x1f2026-08-07T18:00:00+00:00\x1f\x1e",
            )
        ]
    )

    GitContextSubprocessLoader(runner=runner).list_commits(GitContextLogCount(count=3))

    assert runner.calls == [
        (
            (
                "git",
                "--no-pager",
                "log",
                "--max-count=3",
                "--format=%H%x1f%h%x1f%s%x1f%aI%x1f%D%x1e",
                "HEAD",
            ),
            None,
            10.0,
        )
    ]


def test_commit_details_validates_commit_before_loading_metadata_and_message() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(
                returncode=0,
                stdout="abcdef123456\x1fabcdef1\x1fparent1 parent2\x1fAda <ada@example.com>\x1f"
                "2026-08-07T18:00:00+00:00\x1f2026-08-07T18:01:00+00:00\x1f"
                "Add context\x1fHEAD -> main\x1fBody line 1\nBody line 2",
            ),
        ]
    )

    details = GitContextSubprocessLoader(
        working_directory=Path("repo"), timeout_seconds=2.5, runner=runner
    ).load_commit_details("HEAD~1")

    assert details.commit_hash == "abcdef123456"
    assert details.short_hash == "abcdef1"
    assert details.parents == ("parent1", "parent2")
    assert details.author == "Ada <ada@example.com>"
    assert details.author_date == "2026-08-07T18:00:00+00:00"
    assert details.committer_date == "2026-08-07T18:01:00+00:00"
    assert details.subject == "Add context"
    assert details.refs == ("HEAD -> main",)
    assert details.body == "Body line 1\nBody line 2"
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD~1^{commit}"), Path("repo"), 2.5),
        (
            (
                "git",
                "--no-pager",
                "show",
                "--no-patch",
                "--format=%H%x1f%h%x1f%P%x1f%an <%ae>%x1f%aI%x1f%cI%x1f%s%x1f%D%x1f%B",
                "HEAD~1",
            ),
            Path("repo"),
            2.5,
        ),
    ]


def test_commit_details_rejects_invalid_commit_before_loading_details() -> None:
    runner = FakeGitRunner(results=[GitCommandResult(returncode=1, stderr="fatal: bad revision private/ref")])

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).load_commit_details("missing")

    assert exc_info.value.category is GitContextFailureCategory.INVALID_COMMIT
    assert "private/ref" not in str(exc_info.value.metadata)
    assert runner.calls == [(("git", "--no-pager", "rev-parse", "--verify", "--quiet", "missing^{commit}"), None, 10.0)]


@pytest.mark.parametrize("method_name", ["list_commits", "load_commit_details"])
def test_commit_context_maps_malformed_output_safely(method_name: str) -> None:
    results = [GitCommandResult(returncode=0, stdout="malformed")]
    loader = GitContextSubprocessLoader(runner=FakeGitRunner(results=results))
    if method_name == "load_commit_details":
        results.insert(0, GitCommandResult(returncode=0, stdout="abcdef123456\n"))
        action = lambda_load_commit_details(loader)
    else:
        action = loader.list_commits

    with pytest.raises(GitContextLoadError) as exc_info:
        action()

    assert exc_info.value.category is GitContextFailureCategory.GIT_FAILED
    assert "malformed" not in str(exc_info.value.metadata)


def lambda_load_commit_details(loader: GitContextSubprocessLoader):
    """Return a no-argument action that loads HEAD commit details."""

    def load_head_details() -> object:
        return loader.load_commit_details("HEAD")

    return load_head_details


def test_commit_log_maps_non_zero_git_failure_without_raw_stderr() -> None:
    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(
            runner=FakeGitRunner(results=[GitCommandResult(returncode=128, stderr="fatal: private path")])
        ).list_commits()

    assert exc_info.value.category is GitContextFailureCategory.GIT_FAILED
    assert "private path" not in str(exc_info.value.metadata)
