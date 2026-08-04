"""Application DTOs for staged git change context."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from types import MappingProxyType

from fabrica.features.agent_runtime.application.dtos.runtime import (
    MAX_CONTEXT_TEXT_CHARS,
    LocalAgentContextBlock,
    SafeRuntimeMetadataValue,
)

DEFAULT_MAX_STAGED_DIFF_CHARS = MAX_CONTEXT_TEXT_CHARS
STAGED_DIFF_CONTEXT_LABEL = "Git staged diff"


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
        if self.max_chars > MAX_CONTEXT_TEXT_CHARS:
            msg = "max_chars exceeds the local runtime context block bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GitStagedDiff:
    """Bounded staged git diff text prepared for runtime context."""

    text: str
    bounds: GitStagedDiffBounds = field(default_factory=GitStagedDiffBounds)
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text.strip():
            msg = "staged git diff must not be empty"
            raise ValueError(msg)
        if len(self.text) > self.bounds.max_chars:
            msg = "staged git diff exceeds the configured bound"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_context_block(self) -> LocalAgentContextBlock:
        """Return the staged diff as a bounded local runtime context block."""
        return LocalAgentContextBlock(
            text=self.text,
            label=STAGED_DIFF_CONTEXT_LABEL,
            metadata={
                "source": "git_staged_diff",
                "char_count": len(self.text),
                **self.metadata,
            },
        )


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
