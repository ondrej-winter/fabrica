"""Tests for read-only git context command builders."""

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.context_commands import (
    GIT_BRANCH_AHEAD_BEHIND_DEFAULT_ARGV,
    GIT_COMMIT_DETAILS_FORMAT,
    GIT_COMMIT_LOG_FORMAT,
    GIT_CONTEXT_STATUS_SUMMARY_ARGV,
    GIT_HEAD_SHORT_HASH_ARGV,
    GIT_MERGE_BASE_ARGV_PREFIX,
    GIT_UNSTAGED_DIFF_ARGV,
    GIT_UNSTAGED_FILE_LIST_ARGV,
    git_branch_ahead_behind_argv,
    git_commit_changed_files_argv,
    git_commit_details_argv,
    git_commit_diff_argv,
    git_commit_file_diff_argv,
    git_commit_log_argv,
    git_commit_validation_argv,
    git_merge_base_argv,
    git_ref_changed_files_argv,
    git_ref_diff_argv,
    git_ref_file_diff_argv,
    git_ref_validation_argv,
    git_unstaged_file_diff_argv,
)
from fabrica.features.developer_workflow.application.dtos import GitContextLogCount

MUTATING_OR_NETWORK_COMMANDS = {
    "add",
    "checkout",
    "commit",
    "fetch",
    "merge",
    "pull",
    "push",
    "rebase",
    "reset",
    "stash",
    "switch",
    "tag",
}


def assert_read_only_git_argv(argv: tuple[str, ...]) -> None:
    """Assert a read-only git argv follows the no-pager fixed-command contract."""
    assert argv[:2] == ("git", "--no-pager")
    assert not MUTATING_OR_NETWORK_COMMANDS.intersection(argv[2:])


def test_worktree_command_builders_use_fixed_no_pager_argv_and_path_separator() -> None:
    assert GIT_CONTEXT_STATUS_SUMMARY_ARGV == ("git", "--no-pager", "status", "--short", "--branch")
    assert GIT_HEAD_SHORT_HASH_ARGV == ("git", "--no-pager", "rev-parse", "--short", "HEAD")
    assert GIT_UNSTAGED_FILE_LIST_ARGV == ("git", "--no-pager", "diff", "--name-status")
    assert GIT_UNSTAGED_DIFF_ARGV == ("git", "--no-pager", "diff")
    assert git_unstaged_file_diff_argv("--stat") == ("git", "--no-pager", "diff", "--", "--stat")

    for argv in (
        GIT_CONTEXT_STATUS_SUMMARY_ARGV,
        GIT_HEAD_SHORT_HASH_ARGV,
        GIT_UNSTAGED_FILE_LIST_ARGV,
        GIT_UNSTAGED_DIFF_ARGV,
        git_unstaged_file_diff_argv("src/file.py"),
    ):
        assert_read_only_git_argv(argv)


@pytest.mark.parametrize("path", ["", "/absolute.py", "../secret.py", "src/../file.py", "."])
def test_path_based_builders_validate_safe_relative_paths(path: str) -> None:
    with pytest.raises(ValueError, match="git context path"):
        git_unstaged_file_diff_argv(path)
    with pytest.raises(ValueError, match="git context path"):
        git_commit_file_diff_argv("HEAD", path)
    with pytest.raises(ValueError, match="git context path"):
        git_ref_file_diff_argv("main", "HEAD", path)


def test_commit_context_builders_use_fixed_formats_and_validation_commands() -> None:
    assert git_commit_validation_argv("HEAD") == (
        "git",
        "--no-pager",
        "rev-parse",
        "--verify",
        "--quiet",
        "HEAD^{commit}",
    )
    assert git_commit_log_argv(GitContextLogCount(count=3)) == (
        "git",
        "--no-pager",
        "log",
        "--max-count=3",
        f"--format={GIT_COMMIT_LOG_FORMAT}",
        "HEAD",
    )
    assert git_commit_details_argv("HEAD~1") == (
        "git",
        "--no-pager",
        "show",
        "--no-patch",
        f"--format={GIT_COMMIT_DETAILS_FORMAT}",
        "HEAD~1",
    )
    assert git_commit_changed_files_argv("HEAD") == (
        "git",
        "--no-pager",
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        "HEAD",
    )
    assert git_commit_diff_argv("HEAD") == ("git", "--no-pager", "show", "--format=", "--no-ext-diff", "HEAD")
    assert git_commit_file_diff_argv("HEAD", "src/file.py") == (
        "git",
        "--no-pager",
        "show",
        "--format=",
        "--no-ext-diff",
        "HEAD",
        "--",
        "src/file.py",
    )


def test_ref_context_builders_use_three_dot_ranges_and_read_only_ref_helpers() -> None:
    assert git_ref_validation_argv("origin/main") == (
        "git",
        "--no-pager",
        "rev-parse",
        "--verify",
        "--quiet",
        "origin/main^{commit}",
    )
    assert git_ref_changed_files_argv("origin/main", "HEAD") == (
        "git",
        "--no-pager",
        "diff",
        "--name-status",
        "origin/main...HEAD",
    )
    assert git_ref_diff_argv("origin/main", "HEAD") == (
        "git",
        "--no-pager",
        "diff",
        "--no-ext-diff",
        "origin/main...HEAD",
    )
    assert git_ref_file_diff_argv("origin/main", "HEAD", "src/file.py") == (
        "git",
        "--no-pager",
        "diff",
        "--no-ext-diff",
        "origin/main...HEAD",
        "--",
        "src/file.py",
    )
    assert GIT_BRANCH_AHEAD_BEHIND_DEFAULT_ARGV == (
        "git",
        "--no-pager",
        "rev-list",
        "--left-right",
        "--count",
        "@{upstream}...HEAD",
    )
    assert git_branch_ahead_behind_argv("origin/main") == (
        "git",
        "--no-pager",
        "rev-list",
        "--left-right",
        "--count",
        "origin/main...HEAD",
    )
    assert GIT_MERGE_BASE_ARGV_PREFIX == ("git", "--no-pager", "merge-base")
    assert git_merge_base_argv("origin/main", "HEAD") == ("git", "--no-pager", "merge-base", "origin/main", "HEAD")


def test_all_builders_avoid_mutating_and_network_git_commands() -> None:
    commands = (
        GIT_CONTEXT_STATUS_SUMMARY_ARGV,
        GIT_HEAD_SHORT_HASH_ARGV,
        GIT_UNSTAGED_FILE_LIST_ARGV,
        GIT_UNSTAGED_DIFF_ARGV,
        git_unstaged_file_diff_argv("src/file.py"),
        git_commit_validation_argv("HEAD"),
        git_commit_log_argv(),
        git_commit_details_argv("HEAD"),
        git_commit_changed_files_argv("HEAD"),
        git_commit_diff_argv("HEAD"),
        git_commit_file_diff_argv("HEAD", "src/file.py"),
        git_ref_validation_argv("origin/main"),
        git_ref_changed_files_argv("origin/main", "HEAD"),
        git_ref_diff_argv("origin/main", "HEAD"),
        git_ref_file_diff_argv("origin/main", "HEAD", "src/file.py"),
        git_branch_ahead_behind_argv(),
        git_branch_ahead_behind_argv("origin/main"),
        git_merge_base_argv("origin/main", "HEAD"),
    )

    for argv in commands:
        assert_read_only_git_argv(argv)
