"""Fixed git argv builders for read-only repository context inspection."""

from fabrica.features.developer_workflow.application.dtos import GitContextLogCount, validate_git_context_relative_path

DEFAULT_GIT_CONTEXT_TIMEOUT_SECONDS = 10.0

GIT_CONTEXT_STATUS_SUMMARY_ARGV = ("git", "--no-pager", "status", "--short", "--branch")
GIT_HEAD_SHORT_HASH_ARGV = ("git", "--no-pager", "rev-parse", "--short", "HEAD")
GIT_UNSTAGED_FILE_LIST_ARGV = ("git", "--no-pager", "diff", "--name-status")
GIT_UNSTAGED_DIFF_ARGV = ("git", "--no-pager", "diff")

GIT_COMMIT_LOG_FORMAT = "%H%x1f%h%x1f%s%x1f%aI%x1f%D%x1e"
GIT_COMMIT_DETAILS_FORMAT = "%H%x1f%h%x1f%P%x1f%an <%ae>%x1f%aI%x1f%cI%x1f%s%x1f%D%x1f%B"

GIT_MERGE_BASE_ARGV_PREFIX = ("git", "--no-pager", "merge-base")
GIT_BRANCH_AHEAD_BEHIND_DEFAULT_ARGV = (
    "git",
    "--no-pager",
    "rev-list",
    "--left-right",
    "--count",
    "@{upstream}...HEAD",
)


def git_unstaged_file_diff_argv(path: str) -> tuple[str, ...]:
    """Build argv for one safe relative unstaged file diff."""
    return (*GIT_UNSTAGED_DIFF_ARGV, "--", validate_git_context_relative_path(path))


def git_commit_validation_argv(commit: str) -> tuple[str, ...]:
    """Build argv that validates a commit-ish resolves to a commit object."""
    return ("git", "--no-pager", "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")


def git_commit_log_argv(count: GitContextLogCount | None = None) -> tuple[str, ...]:
    """Build argv for bounded recent commit metadata from HEAD."""
    bounded_count = count or GitContextLogCount()
    return (
        "git",
        "--no-pager",
        "log",
        f"--max-count={bounded_count.count}",
        f"--format={GIT_COMMIT_LOG_FORMAT}",
        "HEAD",
    )


def git_commit_details_argv(commit: str) -> tuple[str, ...]:
    """Build argv for one commit's metadata and message without diff output."""
    return ("git", "--no-pager", "show", "--no-patch", f"--format={GIT_COMMIT_DETAILS_FORMAT}", commit)


def git_commit_changed_files_argv(commit: str) -> tuple[str, ...]:
    """Build argv for files changed by one commit without raw diff output."""
    return ("git", "--no-pager", "diff-tree", "--no-commit-id", "--name-status", "-r", commit)


def git_commit_diff_argv(commit: str) -> tuple[str, ...]:
    """Build argv for one commit's raw diff using fixed read-only flags."""
    return ("git", "--no-pager", "show", "--format=", "--no-ext-diff", commit)


def git_commit_file_diff_argv(commit: str, path: str) -> tuple[str, ...]:
    """Build argv for one safe relative file diff in one commit."""
    return (*git_commit_diff_argv(commit), "--", validate_git_context_relative_path(path))


def git_ref_validation_argv(ref: str) -> tuple[str, ...]:
    """Build argv that validates a ref resolves to a commit object."""
    return ("git", "--no-pager", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")


def git_ref_changed_files_argv(base_ref: str, head_ref: str) -> tuple[str, ...]:
    """Build argv for changed files between two refs using v1 three-dot semantics."""
    return ("git", "--no-pager", "diff", "--name-status", _three_dot_range(base_ref, head_ref))


def git_ref_diff_argv(base_ref: str, head_ref: str) -> tuple[str, ...]:
    """Build argv for a bounded full diff between two refs using v1 three-dot semantics."""
    return ("git", "--no-pager", "diff", "--no-ext-diff", _three_dot_range(base_ref, head_ref))


def git_ref_file_diff_argv(base_ref: str, head_ref: str, path: str) -> tuple[str, ...]:
    """Build argv for one safe relative file diff between two refs."""
    return (*git_ref_diff_argv(base_ref, head_ref), "--", validate_git_context_relative_path(path))


def git_branch_ahead_behind_argv(base_ref: str | None = None) -> tuple[str, ...]:
    """Build argv for current branch ahead/behind counts without fetching."""
    if base_ref is None:
        return GIT_BRANCH_AHEAD_BEHIND_DEFAULT_ARGV
    return ("git", "--no-pager", "rev-list", "--left-right", "--count", _three_dot_range(base_ref, "HEAD"))


def git_merge_base_argv(base_ref: str, head_ref: str) -> tuple[str, ...]:
    """Build argv for the merge base of two refs without mutating refs."""
    return (*GIT_MERGE_BASE_ARGV_PREFIX, base_ref, head_ref)


def _three_dot_range(base_ref: str, head_ref: str) -> str:
    return f"{base_ref}...{head_ref}"
