"""Command builders for explicit pre-commit execution."""

from fabrica.features.developer_workflow.application.dtos import PreCommitRunCommand

DEFAULT_PRE_COMMIT_TIMEOUT_SECONDS = 120.0
GIT_REV_PARSE_SHOW_TOPLEVEL_ARGV = ("git", "--no-pager", "rev-parse", "--show-toplevel")
PRE_COMMIT_RUN_ARGV_PREFIX = ("uv", "run", "pre-commit", "run")


def pre_commit_run_argv(command: PreCommitRunCommand) -> tuple[str, ...]:
    """Build argv for a narrow pre-commit invocation."""
    argv = PRE_COMMIT_RUN_ARGV_PREFIX
    if command.hook_id is not None:
        argv = (*argv, command.hook_id)
    if command.all_files:
        argv = (*argv, "--all-files")
    return argv
