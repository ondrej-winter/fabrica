"""Tests for the read-only git context subprocess adapter foundation."""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess import (
    GitCommandResult,
    GitContextSubprocessLoader,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitContextChangedFile,
    GitContextChangedFileList,
    GitContextChangedFileStatus,
    GitContextDiff,
    GitContextDiffBounds,
    GitContextFailureCategory,
)
from fabrica.features.developer_workflow.application.ports import GitContextLoadError

GIT_FAILURE_RETURNCODE = 128


@dataclass
class FakeGitRunner:
    """Deterministic fake for the adapter-local git runner boundary."""

    result: GitCommandResult | None = None
    results: list[GitCommandResult] = field(default_factory=list)
    error: BaseException | None = None
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        if self.error is not None:
            raise self.error
        if self.results:
            return self.results.pop(0)
        return self.result or GitCommandResult(returncode=0, stdout="ok")


class ProbeGitContextSubprocessLoader(GitContextSubprocessLoader):
    """Expose protected foundation hooks for focused unit tests."""

    def run_probe(self, argv: tuple[str, ...]) -> tuple[GitCommandResult, float]:
        """Run one fixed argv through the shared runner hook."""
        return self._run_git(argv)

    def decode_probe(self, value: str | bytes) -> str:
        """Decode one subprocess stream through the shared decode hook."""
        return self._decode(value)

    def ensure_commit_probe(self, commit: str) -> None:
        """Validate one commit-ish through the shared commit validator."""
        self._ensure_commit(commit)

    def ensure_ref_probe(self, ref: str) -> None:
        """Validate one ref through the shared ref validator."""
        self._ensure_ref(ref)

    def ensure_changed_path_probe(self, path: str, changed_files: GitContextChangedFileList) -> str:
        """Validate one changed path through the shared membership hook."""
        return self._ensure_changed_path(path, changed_files)

    def bounded_diff_probe(self, text: str, *, suggestion: str | None = None) -> GitContextDiff:
        """Build a bounded diff through the shared diff hook."""
        return self._bounded_diff(text, duration_seconds=1.2345678, suggestion=suggestion)

    def non_zero_probe(self, stderr: str) -> GitContextLoadError:
        """Map a generic non-zero git result through the shared error hook."""
        return self._non_zero_error(stderr=stderr, returncode=GIT_FAILURE_RETURNCODE, duration_seconds=1.0)


def test_context_adapter_runner_uses_configured_cwd_timeout_and_fixed_argv() -> None:
    runner = FakeGitRunner(result=GitCommandResult(returncode=0, stdout="ok"))

    result, _duration_seconds = ProbeGitContextSubprocessLoader(
        working_directory=Path("repo"),
        timeout_seconds=2.5,
        runner=runner,
    ).run_probe(("git", "--no-pager", "status", "--short", "--branch"))

    assert result.stdout == "ok"
    assert runner.calls == [(("git", "--no-pager", "status", "--short", "--branch"), Path("repo"), 2.5)]


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (FileNotFoundError("git"), GitContextFailureCategory.GIT_UNAVAILABLE),
        (
            subprocess.TimeoutExpired(cmd=["git", "status"], timeout=1.0),
            GitContextFailureCategory.TIMED_OUT,
        ),
        (OSError("boom"), GitContextFailureCategory.GIT_FAILED),
    ],
)
def test_context_adapter_maps_subprocess_failures(error: BaseException, category: GitContextFailureCategory) -> None:
    with pytest.raises(GitContextLoadError) as exc_info:
        ProbeGitContextSubprocessLoader(runner=FakeGitRunner(error=error)).run_probe(("git", "--no-pager", "status"))

    assert exc_info.value.category is category
    assert exc_info.value.metadata["category"] == category.value


def test_context_adapter_maps_decode_failure_without_raw_output_metadata() -> None:
    with pytest.raises(GitContextLoadError) as exc_info:
        ProbeGitContextSubprocessLoader().decode_probe(b"\xff")

    assert exc_info.value.category is GitContextFailureCategory.DECODE_ERROR
    assert "\xff" not in str(exc_info.value.metadata)


def test_context_adapter_maps_not_repository_from_non_zero_stderr_without_raw_diagnostics() -> None:
    error = ProbeGitContextSubprocessLoader().non_zero_probe("fatal: not a git repository: /private/repo")

    assert error.category is GitContextFailureCategory.NOT_A_REPOSITORY
    assert "/private/repo" not in str(error.metadata)


def test_context_adapter_maps_generic_non_zero_failure_safely() -> None:
    error = ProbeGitContextSubprocessLoader().non_zero_probe("fatal: private detail")

    assert error.category is GitContextFailureCategory.GIT_FAILED
    assert error.metadata["returncode"] == GIT_FAILURE_RETURNCODE
    assert "private detail" not in str(error.metadata)


@pytest.mark.parametrize(
    ("probe_name", "argument", "category", "expected_argv"),
    [
        (
            "ensure_commit_probe",
            "missing-commit",
            GitContextFailureCategory.INVALID_COMMIT,
            ("git", "--no-pager", "rev-parse", "--verify", "--quiet", "missing-commit^{commit}"),
        ),
        (
            "ensure_ref_probe",
            "missing-ref",
            GitContextFailureCategory.INVALID_REF,
            ("git", "--no-pager", "rev-parse", "--verify", "--quiet", "missing-ref^{commit}"),
        ),
    ],
)
def test_context_adapter_validates_commits_and_refs_before_inspection(
    probe_name: str,
    argument: str,
    category: GitContextFailureCategory,
    expected_argv: tuple[str, ...],
) -> None:
    runner = FakeGitRunner(result=GitCommandResult(returncode=1, stderr="fatal: bad revision private/ref"))
    loader = ProbeGitContextSubprocessLoader(runner=runner)

    with pytest.raises(GitContextLoadError) as exc_info:
        getattr(loader, probe_name)(argument)

    assert exc_info.value.category is category
    assert "private/ref" not in str(exc_info.value.metadata)
    assert runner.calls == [(expected_argv, None, 10.0)]


def test_context_adapter_changed_path_validation_returns_safe_matching_path() -> None:
    changed_files = GitContextChangedFileList(
        files=(GitContextChangedFile(path="src/file.py", status=GitContextChangedFileStatus.MODIFIED),),
    )

    path = ProbeGitContextSubprocessLoader().ensure_changed_path_probe("src/file.py", changed_files)

    assert path == "src/file.py"


@pytest.mark.parametrize(
    ("path", "category"),
    [
        ("../secret.py", GitContextFailureCategory.INVALID_ARGUMENT),
        ("docs/other.md", GitContextFailureCategory.NO_MATCHING_CHANGES),
    ],
)
def test_context_adapter_changed_path_validation_maps_safe_failures(
    path: str,
    category: GitContextFailureCategory,
) -> None:
    changed_files = GitContextChangedFileList(
        files=(GitContextChangedFile(path="src/file.py", status=GitContextChangedFileStatus.MODIFIED),),
    )

    with pytest.raises(GitContextLoadError) as exc_info:
        ProbeGitContextSubprocessLoader().ensure_changed_path_probe(path, changed_files)

    assert exc_info.value.category is category
    assert path not in str(exc_info.value.metadata)


def test_context_adapter_bounded_diff_adds_safe_metadata() -> None:
    diff = ProbeGitContextSubprocessLoader().bounded_diff_probe(
        "diff --git a/file.py b/file.py\n",
        suggestion="Use git_commit_changed_files first.",
    )

    assert diff.metadata == {
        "duration_seconds": 1.234568,
        "suggestion": "Use git_commit_changed_files first.",
    }


def test_context_adapter_oversized_diff_maps_to_safe_failure_with_suggestion() -> None:
    with pytest.raises(GitContextLoadError) as exc_info:
        ProbeGitContextSubprocessLoader(bounds=GitContextDiffBounds(max_chars=5)).bounded_diff_probe(
            "abcdef",
            suggestion="Use a file diff.",
        )

    assert exc_info.value.category is GitContextFailureCategory.OVERSIZED_OUTPUT
    assert exc_info.value.metadata["suggestion"] == "Use a file diff."
    assert "abcdef" not in str(exc_info.value.metadata)


def test_context_adapter_verbose_diagnostics_can_include_working_directory() -> None:
    error = ProbeGitContextSubprocessLoader(
        working_directory=Path("repo"),
        verbose_diagnostics=True,
    ).non_zero_probe("fatal: unexpected")

    assert error.metadata["diagnostic_mode"] == "verbose"
    assert error.metadata["working_directory"] == "repo"


def test_context_adapter_is_exported_from_git_subprocess_package() -> None:
    assert GitContextSubprocessLoader.__name__ == "GitContextSubprocessLoader"
