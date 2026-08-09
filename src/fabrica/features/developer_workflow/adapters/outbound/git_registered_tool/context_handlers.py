"""Tool handlers for read-only git context inspection."""

from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import SafeRuntimeMetadataValue
from fabrica.features.developer_workflow.application.dtos import (
    GitBranchAheadBehind,
    GitCommitDetails,
    GitCommitLog,
    GitContextChangedFileList,
    GitContextDiff,
    GitContextLogCount,
    GitMergeBase,
    GitStatusSummary,
)
from fabrica.features.developer_workflow.application.ports import (
    GitCommitContextLoader,
    GitContextLoadError,
    GitRefContextLoader,
    GitWorktreeContextLoader,
)

_GIT_CONTEXT_TOOL_FAILURE_MESSAGE = "read-only git context could not be loaded"


def handle_status_summary(loader: GitWorktreeContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return a deterministic text summary for a registered status tool call."""
    _require_no_arguments(arguments, tool_name="git_status_summary")
    try:
        return _format_status_summary(loader.load_status_summary())
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_unstaged_files(loader: GitWorktreeContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return unstaged changed-file lines for a registered tool call."""
    _require_no_arguments(arguments, tool_name="git_unstaged_files")
    try:
        return _format_changed_files(loader.list_unstaged_files())
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_unstaged_diff(loader: GitWorktreeContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return full unstaged diff text for a registered tool call."""
    _require_no_arguments(arguments, tool_name="git_unstaged_diff")
    try:
        return _format_diff(loader.load_unstaged_diff())
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_unstaged_file_diff(
    loader: GitWorktreeContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]
) -> str:
    """Return one unstaged file diff for a registered tool call."""
    path = _require_string_argument(arguments, "path", tool_name="git_unstaged_file_diff")
    try:
        return _format_diff(loader.load_unstaged_file_diff(path))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_commit_log(loader: GitCommitContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return recent commit metadata for a registered tool call."""
    count = _optional_int_argument(arguments, "count", tool_name="git_commit_log")
    try:
        return _format_commit_log(loader.list_commits(GitContextLogCount(count) if count is not None else None))
    except (GitContextLoadError, ValueError) as err:
        if isinstance(err, ValueError):
            raise
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_commit_details(loader: GitCommitContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return one commit's metadata and message for a registered tool call."""
    commit = _require_string_argument(arguments, "commit", tool_name="git_commit_details")
    try:
        return _format_commit_details(loader.load_commit_details(commit))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_commit_changed_files(
    loader: GitCommitContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]
) -> str:
    """Return changed-file lines for one commit registered tool call."""
    commit = _require_string_argument(arguments, "commit", tool_name="git_commit_changed_files")
    try:
        return _format_changed_files(loader.list_commit_changed_files(commit))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_commit_diff(loader: GitCommitContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return full commit diff text for a registered tool call."""
    commit = _require_string_argument(arguments, "commit", tool_name="git_commit_diff")
    try:
        return _format_diff(loader.load_commit_diff(commit))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_commit_file_diff(loader: GitCommitContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return one commit file diff for a registered tool call."""
    commit, path = _require_string_arguments(arguments, ("commit", "path"), tool_name="git_commit_file_diff")
    try:
        return _format_diff(loader.load_commit_file_diff(commit, path))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_ref_changed_files(loader: GitRefContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return changed-file lines for a ref-pair registered tool call."""
    base_ref, head_ref = _require_string_arguments(
        arguments, ("base_ref", "head_ref"), tool_name="git_ref_changed_files"
    )
    try:
        return _format_changed_files(loader.list_ref_changed_files(base_ref, head_ref))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_ref_diff(loader: GitRefContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return full ref diff text for a registered tool call."""
    base_ref, head_ref = _require_string_arguments(arguments, ("base_ref", "head_ref"), tool_name="git_ref_diff")
    try:
        return _format_diff(loader.load_ref_diff(base_ref, head_ref))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_ref_file_diff(loader: GitRefContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return one ref file diff for a registered tool call."""
    base_ref, head_ref, path = _require_string_arguments(
        arguments, ("base_ref", "head_ref", "path"), tool_name="git_ref_file_diff"
    )
    try:
        return _format_diff(loader.load_ref_file_diff(base_ref, head_ref, path))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_branch_ahead_behind(loader: GitRefContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return branch ahead/behind counts for a registered tool call."""
    base_ref = _optional_string_argument(arguments, "base_ref", tool_name="git_branch_ahead_behind")
    try:
        return _format_branch_ahead_behind(loader.load_branch_ahead_behind(base_ref))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def handle_merge_base(loader: GitRefContextLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return merge-base hashes for a registered tool call."""
    base_ref, head_ref = _require_string_arguments(arguments, ("base_ref", "head_ref"), tool_name="git_merge_base")
    try:
        return _format_merge_base(loader.load_merge_base(base_ref, head_ref))
    except GitContextLoadError as err:
        raise RuntimeError(_GIT_CONTEXT_TOOL_FAILURE_MESSAGE) from err


def _format_status_summary(summary: GitStatusSummary) -> str:
    branch = "DETACHED" if summary.is_detached else (summary.branch or "UNKNOWN")
    lines = [
        f"branch\t{branch}",
        f"head_short_hash\t{summary.head_short_hash or ''}",
        f"upstream\t{summary.upstream or ''}",
        f"staged_count\t{summary.staged_count}",
        f"unstaged_count\t{summary.unstaged_count}",
        f"untracked_count\t{summary.untracked_count}",
    ]
    lines.extend(f"staged\t{path}" for path in summary.staged_paths)
    lines.extend(f"unstaged\t{path}" for path in summary.unstaged_paths)
    lines.extend(f"untracked\t{path}" for path in summary.untracked_paths)
    return "\n".join(lines)


def _format_changed_files(changed_files: GitContextChangedFileList) -> str:
    lines = []
    for file in changed_files.files:
        suffix = f"\told_path={file.old_path}" if file.old_path is not None else ""
        lines.append(f"{file.status.value}\t{file.path}{suffix}")
    return "\n".join(lines)


def _format_diff(diff: GitContextDiff) -> str:
    return diff.text


def _format_commit_log(log: GitCommitLog) -> str:
    return "\n".join(
        f"{commit.short_hash}\t{commit.author_date}\t{commit.subject}\trefs={','.join(commit.refs)}"
        for commit in log.commits
    )


def _format_commit_details(details: GitCommitDetails) -> str:
    lines = [
        f"commit\t{details.commit_hash}",
        f"short_hash\t{details.short_hash}",
        f"parents\t{' '.join(details.parents)}",
        f"author\t{details.author}",
        f"author_date\t{details.author_date}",
        f"committer_date\t{details.committer_date}",
        f"refs\t{','.join(details.refs)}",
        f"subject\t{details.subject}",
    ]
    if details.body:
        lines.extend(("body", details.body))
    return "\n".join(lines)


def _format_branch_ahead_behind(result: GitBranchAheadBehind) -> str:
    return "\n".join(
        (
            f"current_branch\t{result.current_branch}",
            f"base_ref\t{result.base_ref}",
            f"ahead_count\t{result.ahead_count}",
            f"behind_count\t{result.behind_count}",
        )
    )


def _format_merge_base(result: GitMergeBase) -> str:
    return "\n".join((f"commit\t{result.commit_hash}", f"short_hash\t{result.short_hash}"))


def _require_no_arguments(arguments: Mapping[str, SafeRuntimeMetadataValue], *, tool_name: str) -> None:
    if arguments:
        msg = f"{tool_name} does not accept arguments"
        raise ValueError(msg)


def _require_string_argument(arguments: Mapping[str, SafeRuntimeMetadataValue], name: str, *, tool_name: str) -> str:
    values = _require_string_arguments(arguments, (name,), tool_name=tool_name)
    return values[0]


def _require_string_arguments(
    arguments: Mapping[str, SafeRuntimeMetadataValue], names: tuple[str, ...], *, tool_name: str
) -> tuple[str, ...]:
    if set(arguments) != set(names):
        msg = f"{tool_name} requires exactly the {', '.join(names)} argument(s)"
        raise ValueError(msg)
    raw_values = tuple(arguments[name] for name in names)
    if not all(isinstance(value, str) for value in raw_values):
        msg = f"{tool_name} string arguments must be strings"
        raise TypeError(msg)
    return tuple(str(value) for value in raw_values)


def _optional_string_argument(
    arguments: Mapping[str, SafeRuntimeMetadataValue], name: str, *, tool_name: str
) -> str | None:
    if not arguments:
        return None
    return _require_string_argument(arguments, name, tool_name=tool_name)


def _optional_int_argument(
    arguments: Mapping[str, SafeRuntimeMetadataValue], name: str, *, tool_name: str
) -> int | None:
    if not arguments:
        return None
    if set(arguments) != {name}:
        msg = f"{tool_name} accepts only the optional {name} argument"
        raise ValueError(msg)
    value = arguments[name]
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"{tool_name} {name} argument must be an integer"
        raise TypeError(msg)
    return value
