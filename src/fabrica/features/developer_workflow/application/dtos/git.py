"""Application DTOs for developer workflow git boundaries."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from types import MappingProxyType

DEFAULT_MAX_STAGED_DIFF_CHARS = 500_000
STAGED_DIFF_CONTEXT_LABEL = "Git staged diff"
SafeGitStagedChangesMetadataValue = str | int | float | bool | None
DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS = 50_000
SafePreCommitMetadataValue = str | int | float | bool | None


class GitStagedFileStatus(StrEnum):
    """Closed staged file status values exposed at the application boundary."""

    ADDED = "A"
    COPIED = "C"
    DELETED = "D"
    MODIFIED = "M"
    RENAMED = "R"
    TYPE_CHANGED = "T"
    UNMERGED = "U"


class GitStagedChangesFailureCategory(StrEnum):
    """Normalized staged git changes failure categories."""

    GIT_UNAVAILABLE = "git_unavailable"
    NOT_A_REPOSITORY = "not_a_repository"
    NO_STAGED_CHANGES = "no_staged_changes"
    OVERSIZED_DIFF = "oversized_diff"
    OVERSIZED_OUTPUT = "oversized_output"
    TIMED_OUT = "timed_out"
    GIT_FAILED = "git_failed"
    DECODE_ERROR = "decode_error"


@dataclass(frozen=True, slots=True)
class GitStagedFile:
    """Validated staged file metadata safe to expose across application boundaries."""

    path: str
    status: GitStagedFileStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _validate_safe_relative_path(self.path))


@dataclass(frozen=True, slots=True)
class GitStagedFileList:
    """Immutable list of validated staged files."""

    files: tuple[GitStagedFile, ...]

    def __post_init__(self) -> None:
        files = tuple(self.files)
        if not files:
            msg = "staged file list must not be empty"
            raise ValueError(msg)
        if len(files) > DEFAULT_MAX_GIT_CONTEXT_CHANGED_FILES:
            msg = "staged file list exceeds the configured bound"
            raise ValueError(msg)
        object.__setattr__(self, "files", files)

    def contains_path(self, path: str) -> bool:
        """Return whether the validated path is included in the staged file list."""
        safe_path = _validate_safe_relative_path(path)
        return any(file.path == safe_path for file in self.files)


@dataclass(frozen=True, slots=True)
class GitStagedDiffBounds:
    """Bounds for staged git diff context loaded into one runtime run."""

    max_chars: int = DEFAULT_MAX_STAGED_DIFF_CHARS

    def __post_init__(self) -> None:
        if self.max_chars < 1:
            msg = "max_chars must be at least 1"
            raise ValueError(msg)
        if self.max_chars > DEFAULT_MAX_STAGED_DIFF_CHARS:
            msg = "max_chars exceeds the staged git diff bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GitStagedDiff:
    """Bounded staged git diff text prepared for runtime context."""

    text: str
    bounds: GitStagedDiffBounds = field(default_factory=GitStagedDiffBounds)
    metadata: Mapping[str, SafeGitStagedChangesMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text.strip():
            msg = "staged git diff must not be empty"
            raise ValueError(msg)
        if len(self.text) > self.bounds.max_chars:
            msg = "staged git diff exceeds the configured bound"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


def _validate_safe_relative_path(path: str) -> str:
    if not path:
        msg = "staged file path must not be empty"
        raise ValueError(msg)
    if path != path.strip():
        msg = "staged file path must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if path == ".":
        msg = "staged file path must not be the current directory"
        raise ValueError(msg)
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute():
        msg = "staged file path must be relative"
        raise ValueError(msg)
    if any(part in {"", ".", ".."} for part in pure_path.parts):
        msg = "staged file path must not contain empty, current, or parent-directory components"
        raise ValueError(msg)
    return path


@dataclass(frozen=True, slots=True)
class CreateGitCommitCommand:
    """Command to create a git commit from an already-approved message."""

    message: str

    def __post_init__(self) -> None:
        if not self.message.strip():
            msg = "commit message must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GitCommitResult:
    """Result returned after an approved git commit attempt succeeds."""

    short_hash: str | None = None

    def __post_init__(self) -> None:
        if self.short_hash is not None:
            short_hash = self.short_hash.strip()
            if not short_hash:
                msg = "short_hash must not be empty when provided"
                raise ValueError(msg)
            object.__setattr__(self, "short_hash", short_hash)


DEFAULT_MAX_GIT_CONTEXT_DIFF_CHARS = 500_000
DEFAULT_GIT_CONTEXT_LOG_COUNT = 20
DEFAULT_MAX_GIT_CONTEXT_CHANGED_FILES = 200
DEFAULT_MAX_GIT_CONTEXT_STATUS_PATHS = 20
DEFAULT_MAX_GIT_COMMIT_MESSAGE_CHARS = 100_000
MAX_GIT_CONTEXT_LOG_COUNT = 50

SafeGitContextMetadataValue = str | int | float | bool | None


class GitContextChangedFileStatus(StrEnum):
    """Closed changed-file status values exposed by read-only git context."""

    ADDED = "A"
    COPIED = "C"
    DELETED = "D"
    MODIFIED = "M"
    RENAMED = "R"
    TYPE_CHANGED = "T"
    UNMERGED = "U"


class GitContextFailureCategory(StrEnum):
    """Normalized read-only git context failure categories."""

    GIT_UNAVAILABLE = "git_unavailable"
    NOT_A_REPOSITORY = "not_a_repository"
    NO_MATCHING_CHANGES = "no_matching_changes"
    INVALID_ARGUMENT = "invalid_argument"
    INVALID_REF = "invalid_ref"
    INVALID_COMMIT = "invalid_commit"
    OVERSIZED_OUTPUT = "oversized_output"
    TIMED_OUT = "timed_out"
    GIT_FAILED = "git_failed"
    DECODE_ERROR = "decode_error"


class PreCommitRunStatus(StrEnum):
    """Normalized pre-commit execution outcomes."""

    PASSED = "passed"
    FAILED = "failed"
    MODIFIED_FILES = "modified_files"


class PreCommitFailureCategory(StrEnum):
    """Application-safe failure categories for pre-commit execution."""

    PRE_COMMIT_UNAVAILABLE = "pre_commit_unavailable"
    NOT_A_REPOSITORY = "not_a_repository"
    TIMED_OUT = "timed_out"
    EXECUTION_FAILED = "execution_failed"
    DECODE_ERROR = "decode_error"
    OVERSIZED_OUTPUT = "oversized_output"


@dataclass(frozen=True, slots=True)
class GitContextChangedFile:
    """Validated changed-file metadata safe to expose across application boundaries."""

    path: str
    status: GitContextChangedFileStatus
    old_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", validate_git_context_relative_path(self.path))
        if self.old_path is not None:
            object.__setattr__(self, "old_path", validate_git_context_relative_path(self.old_path))
        if self.status in {GitContextChangedFileStatus.RENAMED, GitContextChangedFileStatus.COPIED}:
            if self.old_path is None:
                msg = "renamed and copied git context files must include old_path metadata"
                raise ValueError(msg)
        elif self.old_path is not None:
            msg = "old_path metadata is only valid for renamed or copied git context files"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GitContextChangedFileList:
    """Immutable list of validated read-only git changed files."""

    files: tuple[GitContextChangedFile, ...]

    def __post_init__(self) -> None:
        files = tuple(self.files)
        if not files:
            msg = "git context changed-file list must not be empty"
            raise ValueError(msg)
        if len(files) > DEFAULT_MAX_GIT_CONTEXT_CHANGED_FILES:
            msg = "git context changed-file list exceeds the configured bound"
            raise ValueError(msg)
        object.__setattr__(self, "files", files)

    def contains_path(self, path: str) -> bool:
        """Return whether the validated canonical path appears in the changed-file list."""
        safe_path = validate_git_context_relative_path(path)
        return any(file.path == safe_path for file in self.files)


@dataclass(frozen=True, slots=True)
class GitContextDiffBounds:
    """Bounds for read-only git diff context loaded into one runtime run."""

    max_chars: int = DEFAULT_MAX_GIT_CONTEXT_DIFF_CHARS

    def __post_init__(self) -> None:
        if self.max_chars < 1:
            msg = "max_chars must be at least 1"
            raise ValueError(msg)
        if self.max_chars > DEFAULT_MAX_GIT_CONTEXT_DIFF_CHARS:
            msg = "max_chars exceeds the read-only git context diff bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GitContextLogCount:
    """Bounded commit-log count for read-only git history inspection."""

    count: int = DEFAULT_GIT_CONTEXT_LOG_COUNT

    def __post_init__(self) -> None:
        if self.count < 1:
            msg = "count must be at least 1"
            raise ValueError(msg)
        if self.count > MAX_GIT_CONTEXT_LOG_COUNT:
            msg = "count exceeds the read-only git context log bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GitContextDiff:
    """Bounded read-only git diff text prepared for runtime context."""

    text: str
    bounds: GitContextDiffBounds = field(default_factory=GitContextDiffBounds)
    metadata: Mapping[str, SafeGitContextMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text.strip():
            msg = "read-only git context diff must not be empty"
            raise ValueError(msg)
        if len(self.text) > self.bounds.max_chars:
            msg = "read-only git context diff exceeds the configured bound"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GitStatusSummary:
    """Bounded summary of the current git worktree state."""

    branch: str | None
    head_short_hash: str | None
    upstream: str | None = None
    is_detached: bool = False
    staged_count: int = 0
    unstaged_count: int = 0
    untracked_count: int = 0
    staged_paths: tuple[str, ...] = ()
    unstaged_paths: tuple[str, ...] = ()
    untracked_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_non_negative_count(self.staged_count, field_name="staged_count")
        _validate_non_negative_count(self.unstaged_count, field_name="unstaged_count")
        _validate_non_negative_count(self.untracked_count, field_name="untracked_count")
        object.__setattr__(self, "staged_paths", _validate_bounded_paths(self.staged_paths, field_name="staged_paths"))
        object.__setattr__(
            self,
            "unstaged_paths",
            _validate_bounded_paths(self.unstaged_paths, field_name="unstaged_paths"),
        )
        object.__setattr__(
            self,
            "untracked_paths",
            _validate_bounded_paths(self.untracked_paths, field_name="untracked_paths"),
        )


@dataclass(frozen=True, slots=True)
class GitCommitSummary:
    """Bounded metadata for one commit in a read-only git log."""

    commit_hash: str
    short_hash: str
    subject: str
    author_date: str
    refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.commit_hash, field_name="commit_hash")
        _validate_non_empty_text(self.short_hash, field_name="short_hash")
        _validate_non_empty_text(self.subject, field_name="subject")
        _validate_non_empty_text(self.author_date, field_name="author_date")
        object.__setattr__(self, "refs", tuple(self.refs))


@dataclass(frozen=True, slots=True)
class GitCommitLog:
    """Immutable bounded commit-log result."""

    commits: tuple[GitCommitSummary, ...]

    def __post_init__(self) -> None:
        commits = tuple(self.commits)
        if not commits:
            msg = "git commit log must not be empty"
            raise ValueError(msg)
        object.__setattr__(self, "commits", commits)


@dataclass(frozen=True, slots=True)
class GitCommitDetails:
    """Read-only metadata and message details for one commit."""

    commit_hash: str
    short_hash: str
    parents: tuple[str, ...]
    author: str
    author_date: str
    committer_date: str
    subject: str
    body: str = ""
    refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.commit_hash, field_name="commit_hash")
        _validate_non_empty_text(self.short_hash, field_name="short_hash")
        _validate_non_empty_text(self.author, field_name="author")
        _validate_non_empty_text(self.author_date, field_name="author_date")
        _validate_non_empty_text(self.committer_date, field_name="committer_date")
        _validate_non_empty_text(self.subject, field_name="subject")
        if len(self.body) > DEFAULT_MAX_GIT_COMMIT_MESSAGE_CHARS:
            msg = "commit message body exceeds the configured bound"
            raise ValueError(msg)
        object.__setattr__(self, "parents", tuple(self.parents))
        object.__setattr__(self, "refs", tuple(self.refs))


@dataclass(frozen=True, slots=True)
class GitBranchAheadBehind:
    """Ahead/behind counts for the current branch against a base ref."""

    current_branch: str
    base_ref: str
    ahead_count: int
    behind_count: int

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.current_branch, field_name="current_branch")
        _validate_non_empty_text(self.base_ref, field_name="base_ref")
        _validate_non_negative_count(self.ahead_count, field_name="ahead_count")
        _validate_non_negative_count(self.behind_count, field_name="behind_count")


@dataclass(frozen=True, slots=True)
class GitMergeBase:
    """Merge-base hashes for two validated refs."""

    commit_hash: str
    short_hash: str

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.commit_hash, field_name="commit_hash")
        _validate_non_empty_text(self.short_hash, field_name="short_hash")


@dataclass(frozen=True, slots=True)
class PreCommitRunCommand:
    """Command for running a narrow pre-commit hook invocation."""

    hook_id: str | None = None
    all_files: bool = False

    def __post_init__(self) -> None:
        if self.hook_id is not None:
            object.__setattr__(self, "hook_id", validate_pre_commit_hook_id(self.hook_id))


@dataclass(frozen=True, slots=True)
class PreCommitRunResult:
    """Bounded output from one pre-commit execution."""

    status: PreCommitRunStatus
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    metadata: Mapping[str, SafePreCommitMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.stdout) > DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS:
            msg = "pre-commit stdout exceeds the configured bound"
            raise ValueError(msg)
        if len(self.stderr) > DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS:
            msg = "pre-commit stderr exceeds the configured bound"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


def validate_git_context_relative_path(path: str) -> str:
    """Validate a safe relative path for read-only git context operations."""
    if not path:
        msg = "git context path must not be empty"
        raise ValueError(msg)
    if path != path.strip():
        msg = "git context path must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if path == ".":
        msg = "git context path must not be the current directory"
        raise ValueError(msg)
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute():
        msg = "git context path must be relative"
        raise ValueError(msg)
    if any(part in {"", ".", ".."} for part in pure_path.parts):
        msg = "git context path must not contain empty, current, or parent-directory components"
        raise ValueError(msg)
    return path


def validate_git_staged_relative_path(path: str) -> str:
    """Validate a safe relative path for staged git operations."""
    return _validate_safe_relative_path(path)


def validate_pre_commit_hook_id(hook_id: str) -> str:
    """Validate a narrow pre-commit hook identifier, not arbitrary flags."""
    if not hook_id:
        msg = "pre-commit hook id must not be empty"
        raise ValueError(msg)
    if hook_id != hook_id.strip():
        msg = "pre-commit hook id must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if hook_id.startswith("-"):
        msg = "pre-commit hook id must not be a flag"
        raise ValueError(msg)
    allowed_characters = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")
    if any(character not in allowed_characters for character in hook_id):
        msg = "pre-commit hook id contains unsupported characters"
        raise ValueError(msg)
    return hook_id


def _validate_non_empty_text(value: str, *, field_name: str) -> None:
    if not value.strip():
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)


def _validate_non_negative_count(value: int, *, field_name: str) -> None:
    if value < 0:
        msg = f"{field_name} must not be negative"
        raise ValueError(msg)


def _validate_bounded_paths(paths: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    bounded_paths = tuple(validate_git_context_relative_path(path) for path in paths)
    if len(bounded_paths) > DEFAULT_MAX_GIT_CONTEXT_STATUS_PATHS:
        msg = f"{field_name} exceeds the configured bound"
        raise ValueError(msg)
    return bounded_paths
