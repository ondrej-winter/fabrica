"""Git command constants for staged change inspection."""

GIT_STAGED_DIFF_ARGV = ("git", "--no-pager", "diff", "--staged")
GIT_STAGED_FILE_LIST_ARGV = (*GIT_STAGED_DIFF_ARGV, "--name-status")
DEFAULT_GIT_TIMEOUT_SECONDS = 10.0


def git_staged_file_diff_argv(path: str) -> tuple[str, ...]:
    """Build the staged diff command for one path after the git path separator."""
    return (*GIT_STAGED_DIFF_ARGV, "--", path)
