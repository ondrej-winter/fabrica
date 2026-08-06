"""Git command constants for approved commit creation."""

DEFAULT_GIT_COMMIT_TIMEOUT_SECONDS = 10.0
GIT_COMMIT_FILE_ARGV_PREFIX = ("git", "--no-pager", "commit", "--file")
GIT_REV_PARSE_SHORT_HEAD_ARGV = ("git", "--no-pager", "rev-parse", "--short", "HEAD")


def git_commit_file_argv(message_file_path: str) -> tuple[str, ...]:
    """Build argv for committing with an approved temporary message file."""
    return (*GIT_COMMIT_FILE_ARGV_PREFIX, message_file_path)
