"""Immutable DTOs for the workspace-reading application boundary."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

DEFAULT_MAX_FILES_PER_CALL = 20
DEFAULT_MAX_PARALLEL_READS = 8
DEFAULT_MAX_READ_LINES = 2_000
DEFAULT_MAX_LINE_CHARS = 2_000
# Reserve space for the required serialized read-result metadata inside the
# runtime's 48,000-character provider-neutral tool-content part.
DEFAULT_MAX_READ_OUTPUT_CHARS = 46_000
DEFAULT_MAX_TEXT_FILE_BYTES = 100_000_000
DEFAULT_MAX_IMAGE_BYTES = 10_000_000
DEFAULT_MAX_METADATA_SCAN_LINES = 50_000
DEFAULT_PER_FILE_DEADLINE_SECONDS = 10.0
DEFAULT_TOOL_DEADLINE_SECONDS = 20.0
DEFAULT_MAX_RETRIES = 1
MAX_WORKSPACE_PATH_CHARS = 4_096
MAX_ERROR_MESSAGE_CHARS = 1_000

SafeReadMetadataValue = str | int | float | bool | None


class ReadFileType(StrEnum):
    """Supported provider-neutral workspace content types."""

    TEXT = "text"
    IMAGE = "image"


class ReadFileErrorCode(StrEnum):
    """Stable Version 1 error codes for individual read outcomes."""

    INVALID_INPUT = "INVALID_INPUT"
    INVALID_PATH = "INVALID_PATH"
    PATH_OUTSIDE_WORKSPACE = "PATH_OUTSIDE_WORKSPACE"
    NOT_FOUND = "NOT_FOUND"
    NOT_A_FILE = "NOT_A_FILE"
    INVALID_RANGE = "INVALID_RANGE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_BINARY_FILE = "UNSUPPORTED_BINARY_FILE"
    UNSUPPORTED_ENCODING = "UNSUPPORTED_ENCODING"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    IMAGE_INPUT_UNSUPPORTED = "IMAGE_INPUT_UNSUPPORTED"
    READ_TIMEOUT = "READ_TIMEOUT"
    READ_CANCELLED = "READ_CANCELLED"
    IO_ERROR = "IO_ERROR"


@dataclass(frozen=True, slots=True)
class ReadFilesLimits:
    """Bounds for one workspace-reading batch invocation."""

    max_files_per_call: int = DEFAULT_MAX_FILES_PER_CALL
    max_parallel_reads: int = DEFAULT_MAX_PARALLEL_READS
    max_read_lines: int = DEFAULT_MAX_READ_LINES
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS
    max_output_chars_per_file: int = DEFAULT_MAX_READ_OUTPUT_CHARS
    max_text_file_bytes: int = DEFAULT_MAX_TEXT_FILE_BYTES
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES
    max_metadata_scan_lines: int = DEFAULT_MAX_METADATA_SCAN_LINES
    per_file_deadline_seconds: float = DEFAULT_PER_FILE_DEADLINE_SECONDS
    tool_deadline_seconds: float = DEFAULT_TOOL_DEADLINE_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES

    def __post_init__(self) -> None:
        for field_name in (
            "max_files_per_call",
            "max_parallel_reads",
            "max_read_lines",
            "max_line_chars",
            "max_output_chars_per_file",
            "max_text_file_bytes",
            "max_image_bytes",
            "max_metadata_scan_lines",
        ):
            if getattr(self, field_name) < 1:
                msg = f"{field_name} must be at least 1"
                raise ValueError(msg)
        if self.max_parallel_reads > self.max_files_per_call:
            msg = "max_parallel_reads must not exceed max_files_per_call"
            raise ValueError(msg)
        if self.per_file_deadline_seconds <= 0 or self.tool_deadline_seconds <= 0:
            msg = "read deadlines must be positive"
            raise ValueError(msg)
        if self.tool_deadline_seconds < self.per_file_deadline_seconds:
            msg = "tool deadline must not be shorter than the per-file deadline"
            raise ValueError(msg)
        if self.max_retries < 0 or self.max_retries > DEFAULT_MAX_RETRIES:
            msg = "max_retries must be between 0 and 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ReadFileRequest:
    """One canonical workspace-relative file request with inclusive line bounds."""

    path: str
    start_line: int | None = None
    end_line: int | None = None

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")
        _validate_line_number(self.start_line, field_name="start_line")
        _validate_line_number(self.end_line, field_name="end_line")
        if self.start_line is not None and self.end_line is not None and self.start_line > self.end_line:
            msg = "start_line must be less than or equal to end_line"
            raise ValueError(msg)

    @property
    def effective_start_line(self) -> int:
        """Return the defaulted one-based start line."""
        return self.start_line or 1


@dataclass(frozen=True, slots=True)
class ReadFilesCommand:
    """Canonical ordered batch command for workspace file reads."""

    files: tuple[ReadFileRequest, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(self.files))
        if not self.files:
            msg = "files must not be empty"
            raise ValueError(msg)
        if len(self.files) > DEFAULT_MAX_FILES_PER_CALL:
            msg = "files exceeds the safe batch bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ReadFileError:
    """Stable safe error returned for one requested path."""

    code: ReadFileErrorCode
    message: str | None = None
    metadata: Mapping[str, SafeReadMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.message is not None and len(self.message) > MAX_ERROR_MESSAGE_CHARS:
            msg = "read error message exceeds the safe bound"
            raise ValueError(msg)
        metadata = dict(self.metadata)
        for key, value in metadata.items():
            if not key or not key.replace("_", "").isalnum():
                msg = "read error metadata keys must be safe identifiers"
                raise ValueError(msg)
            if not isinstance(value, (str, int, float, bool, type(None))):
                msg = "read error metadata values must be scalar and safe"
                raise TypeError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(metadata))


@dataclass(frozen=True, slots=True)
class ImageContent:
    """Verified provider-neutral image content; encoding is provider-adapter owned."""

    path: str
    media_type: str
    data: bytes

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")
        if self.media_type not in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
            msg = "media_type must be a supported image type"
            raise ValueError(msg)
        if not self.data:
            msg = "image data must not be empty"
            raise ValueError(msg)
        object.__setattr__(self, "data", bytes(self.data))


@dataclass(frozen=True, slots=True)
class TextFileResult:
    """Successful bounded text-file outcome with explicit pagination metadata."""

    path: str
    content: str
    start_line: int | None
    end_line: int | None
    complete: bool
    next_start_line: int | None
    total_lines: int
    total_lines_exact: bool
    truncated_lines: tuple[int, ...] = field(default_factory=tuple)
    type: ReadFileType = field(default=ReadFileType.TEXT, init=False)

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")
        _validate_line_number(self.start_line, field_name="start_line")
        _validate_line_number(self.end_line, field_name="end_line")
        if (self.start_line is None) != (self.end_line is None):
            msg = "empty output must not have a partial line range"
            raise ValueError(msg)
        if self.start_line is not None and self.end_line is not None and self.end_line < self.start_line:
            msg = "end_line must not precede start_line"
            raise ValueError(msg)
        if self.end_line is not None and self.total_lines < self.end_line:
            msg = "total_lines must cover returned lines"
            raise ValueError(msg)
        if self.complete != (self.next_start_line is None):
            msg = "pagination metadata must match complete"
            raise ValueError(msg)
        expected_next_start_line = 1 if self.end_line is None else self.end_line + 1
        if self.next_start_line is not None and self.next_start_line != expected_next_start_line:
            msg = "next_start_line must immediately follow end_line"
            raise ValueError(msg)
        truncated_lines = tuple(self.truncated_lines)
        if self.start_line is None and truncated_lines:
            msg = "empty output must not have truncated lines"
            raise ValueError(msg)
        if (
            self.start_line is not None
            and self.end_line is not None
            and any(line < self.start_line or line > self.end_line for line in truncated_lines)
        ):
            msg = "truncated lines must be returned lines"
            raise ValueError(msg)
        if tuple(sorted(set(truncated_lines))) != truncated_lines:
            msg = "truncated lines must be ordered and unique"
            raise ValueError(msg)
        object.__setattr__(self, "truncated_lines", truncated_lines)


@dataclass(frozen=True, slots=True)
class ImageFileResult:
    """Successful image outcome with verified provider-neutral content."""

    path: str
    image: ImageContent
    type: ReadFileType = field(default=ReadFileType.IMAGE, init=False)

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")
        if self.path != self.image.path:
            msg = "image content path must match the result path"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ReadFileFailure:
    """Non-fatal per-file failure that preserves batch partial success."""

    path: str
    error: ReadFileError
    success: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")


type ReadFileResult = TextFileResult | ImageFileResult | ReadFileFailure


@dataclass(frozen=True, slots=True)
class ReadFilesResult:
    """Ordered aggregate of independent workspace-read outcomes."""

    results: tuple[ReadFileResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", tuple(self.results))
        if not self.results:
            msg = "results must not be empty"
            raise ValueError(msg)
        if len(self.results) > DEFAULT_MAX_FILES_PER_CALL:
            msg = "results exceeds the safe batch bound"
            raise ValueError(msg)


def _validate_workspace_relative_path(value: str, *, field_name: str) -> None:
    if not value or not value.strip():
        msg = f"{field_name} must not be blank"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if len(value) > MAX_WORKSPACE_PATH_CHARS:
        msg = f"{field_name} exceeds the safe path bound"
        raise ValueError(msg)
    if value.startswith(("/", "\\")) or "\\" in value or value in {".", ".."} or ".." in value.split("/"):
        msg = f"{field_name} must be workspace-relative and non-escaping"
        raise ValueError(msg)


def _validate_line_number(value: int | None, *, field_name: str) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
        msg = f"{field_name} must be a one-based integer"
        raise ValueError(msg)
