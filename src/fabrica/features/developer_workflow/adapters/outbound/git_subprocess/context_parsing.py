"""Parsers for read-only git context subprocess output."""

from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_MAX_GIT_CONTEXT_STATUS_PATHS,
    GitBranchAheadBehind,
    GitCommitDetails,
    GitCommitLog,
    GitCommitSummary,
    GitContextChangedFile,
    GitContextChangedFileStatus,
    GitMergeBase,
    GitStatusSummary,
)

FIELD_SEPARATOR = "\x1f"
RECORD_SEPARATOR = "\x1e"
REGULAR_NAME_STATUS_FIELD_COUNT = 2
RENAME_COPY_NAME_STATUS_FIELD_COUNT = 3
COMMIT_LOG_FIELD_COUNT = 5
COMMIT_DETAILS_FIELD_COUNT = 9
AHEAD_BEHIND_FIELD_COUNT = 2
SHORT_HASH_LENGTH = 7
STATUS_BRANCH_PREFIX = "## "


def parse_context_name_status_line(line: str) -> GitContextChangedFile:
    """Parse one `git diff --name-status` line into read-only context metadata."""
    fields = line.split("\t")
    if len(fields) < REGULAR_NAME_STATUS_FIELD_COUNT:
        msg = "git context name-status record must include status and path"
        raise ValueError(msg)
    try:
        status = GitContextChangedFileStatus(fields[0][0])
    except ValueError as err:
        msg = "git context name-status record uses an unsupported status"
        raise ValueError(msg) from err
    if status in {GitContextChangedFileStatus.RENAMED, GitContextChangedFileStatus.COPIED}:
        if len(fields) != RENAME_COPY_NAME_STATUS_FIELD_COUNT:
            msg = "rename and copy context records must include old and new paths"
            raise ValueError(msg)
        return GitContextChangedFile(path=fields[2], status=status, old_path=fields[1])
    if len(fields) != REGULAR_NAME_STATUS_FIELD_COUNT:
        msg = "git context name-status record has unexpected path fields"
        raise ValueError(msg)
    return GitContextChangedFile(path=fields[1], status=status)


def parse_status_summary(
    output: str,
    *,
    head_short_hash: str | None,
    max_paths_per_category: int = DEFAULT_MAX_GIT_CONTEXT_STATUS_PATHS,
) -> GitStatusSummary:
    """Parse `git status --short --branch` output into a bounded worktree summary."""
    branch: str | None = None
    upstream: str | None = None
    is_detached = False
    staged_count = 0
    unstaged_count = 0
    staged_paths: list[str] = []
    unstaged_paths: list[str] = []
    untracked_paths: list[str] = []

    for line in output.splitlines():
        if not line:
            continue
        if line.startswith(STATUS_BRANCH_PREFIX):
            branch, upstream, is_detached = _parse_branch_line(line.removeprefix(STATUS_BRANCH_PREFIX))
            continue
        status = line[:2]
        path = line[3:]
        if status == "??":
            untracked_paths.append(path)
            continue
        if status[0] != " ":
            staged_count += 1
            staged_paths.append(path)
        if status[1] != " ":
            unstaged_count += 1
            unstaged_paths.append(path)

    return GitStatusSummary(
        branch=branch,
        head_short_hash=head_short_hash,
        upstream=upstream,
        is_detached=is_detached,
        staged_count=staged_count,
        unstaged_count=unstaged_count,
        untracked_count=len(untracked_paths),
        staged_paths=tuple(staged_paths[:max_paths_per_category]),
        unstaged_paths=tuple(unstaged_paths[:max_paths_per_category]),
        untracked_paths=tuple(untracked_paths[:max_paths_per_category]),
    )


def parse_commit_log(output: str) -> GitCommitLog:
    """Parse fixed-format `git log` output into commit summaries."""
    commits = tuple(_parse_commit_summary(record) for record in _split_records(output))
    return GitCommitLog(commits=commits)


def parse_commit_details(output: str) -> GitCommitDetails:
    """Parse fixed-format `git show --no-patch` output into one commit detail DTO."""
    fields = output.split(FIELD_SEPARATOR, maxsplit=COMMIT_DETAILS_FIELD_COUNT - 1)
    if len(fields) != COMMIT_DETAILS_FIELD_COUNT:
        msg = "commit details output must include fixed metadata fields"
        raise ValueError(msg)
    return GitCommitDetails(
        commit_hash=fields[0],
        short_hash=fields[1],
        parents=tuple(parent for parent in fields[2].split() if parent),
        author=fields[3],
        author_date=fields[4],
        committer_date=fields[5],
        subject=fields[6],
        refs=_parse_refs(fields[7]),
        body=fields[8].strip(),
    )


def parse_ahead_behind_counts(output: str, *, current_branch: str, base_ref: str) -> GitBranchAheadBehind:
    """Parse `git rev-list --left-right --count base...HEAD` output."""
    fields = output.strip().split()
    if len(fields) != AHEAD_BEHIND_FIELD_COUNT:
        msg = "ahead/behind output must include two counts"
        raise ValueError(msg)
    behind_count, ahead_count = (int(fields[0]), int(fields[1]))
    return GitBranchAheadBehind(
        current_branch=current_branch,
        base_ref=base_ref,
        ahead_count=ahead_count,
        behind_count=behind_count,
    )


def parse_merge_base(output: str) -> GitMergeBase:
    """Parse `git merge-base` output into full and short hashes."""
    commit_hash = output.strip()
    if not commit_hash:
        msg = "merge-base output must include a commit hash"
        raise ValueError(msg)
    return GitMergeBase(commit_hash=commit_hash, short_hash=commit_hash[:SHORT_HASH_LENGTH])


def _parse_commit_summary(record: str) -> GitCommitSummary:
    fields = record.split(FIELD_SEPARATOR)
    if len(fields) != COMMIT_LOG_FIELD_COUNT:
        msg = "commit log record must include fixed metadata fields"
        raise ValueError(msg)
    return GitCommitSummary(
        commit_hash=fields[0],
        short_hash=fields[1],
        subject=fields[2],
        author_date=fields[3],
        refs=_parse_refs(fields[4]),
    )


def _split_records(output: str) -> tuple[str, ...]:
    records = tuple(record.removeprefix("\n") for record in output.split(RECORD_SEPARATOR) if record.strip())
    if not records:
        msg = "git context output must include at least one record"
        raise ValueError(msg)
    return records


def _parse_refs(refs: str) -> tuple[str, ...]:
    return tuple(ref.strip() for ref in refs.split(",") if ref.strip())


def _parse_branch_line(line: str) -> tuple[str | None, str | None, bool]:
    branch_segment = line.split(" [", maxsplit=1)[0]
    if branch_segment == "HEAD (no branch)":
        return None, None, True
    branch, separator, upstream = branch_segment.partition("...")
    return branch or None, upstream if separator and upstream else None, False
