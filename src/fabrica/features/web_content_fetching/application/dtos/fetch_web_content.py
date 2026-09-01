"""Immutable DTOs for the public web-content fetching application boundary."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

DEFAULT_MAX_REQUESTS_PER_CALL = 8
DEFAULT_MAX_PARALLEL_FETCHES = 4
DEFAULT_PER_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 1
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_RESPONSE_BYTES = 5_000_000
DEFAULT_MAX_CONTENT_CHARS = 48_000
DEFAULT_MAX_BATCH_CONTENT_CHARS = 96_000
MIN_REQUEST_CONTENT_CHARS = 1_000
MAX_ERROR_MESSAGE_CHARS = 1_000
MAX_RETRY_AFTER_SECONDS = 60.0
TRUST_UNTRUSTED_WEB_CONTENT = "untrusted_web_content"
MAX_TOOL_TEXT_PARTS = 40
MAX_TOOL_TEXT_PART_CHARS = 48_000
MIN_HTTP_STATUS = 100
MAX_HTTP_STATUS = 599

SafeFetchMetadataValue = str | int | float | bool | None


class FetchContentFormat(StrEnum):
    """Normalized textual formats supported by the fetch result contract."""

    MARKDOWN = "markdown"
    JSON = "json"
    XML = "xml"
    TEXT = "text"


class FetchErrorCode(StrEnum):
    """Stable Version 1 error codes for individual fetch outcomes."""

    INVALID_INPUT = "INVALID_INPUT"
    INVALID_URL = "INVALID_URL"
    UNSUPPORTED_PROTOCOL = "UNSUPPORTED_PROTOCOL"
    INSECURE_REDIRECT = "INSECURE_REDIRECT"
    URL_CREDENTIALS_NOT_ALLOWED = "URL_CREDENTIALS_NOT_ALLOWED"
    DNS_FAILED = "DNS_FAILED"
    DESTINATION_NOT_ALLOWED = "DESTINATION_NOT_ALLOWED"
    TOO_MANY_REDIRECTS = "TOO_MANY_REDIRECTS"
    INVALID_REDIRECT = "INVALID_REDIRECT"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    TLS_ERROR = "TLS_ERROR"
    FETCH_TIMEOUT = "FETCH_TIMEOUT"
    FETCH_CANCELLED = "FETCH_CANCELLED"
    HTTP_ERROR = "HTTP_ERROR"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
    UNSUPPORTED_ENCODING = "UNSUPPORTED_ENCODING"
    INVALID_JSON = "INVALID_JSON"
    CONTENT_EXTRACTION_FAILED = "CONTENT_EXTRACTION_FAILED"
    INTERNAL_FETCH_ERROR = "INTERNAL_FETCH_ERROR"
    PUBLIC_WEB_DISABLED = "PUBLIC_WEB_DISABLED"


@dataclass(frozen=True, slots=True)
class FetchWebContentLimits:
    """Host-configurable bounds for one public-web batch invocation."""

    max_requests_per_call: int = DEFAULT_MAX_REQUESTS_PER_CALL
    max_parallel_fetches: int = DEFAULT_MAX_PARALLEL_FETCHES
    per_request_timeout_seconds: float = DEFAULT_PER_REQUEST_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    max_content_chars_per_request: int = DEFAULT_MAX_CONTENT_CHARS
    max_batch_content_chars: int = DEFAULT_MAX_BATCH_CONTENT_CHARS

    def __post_init__(self) -> None:
        for field_name in (
            "max_requests_per_call",
            "max_parallel_fetches",
            "max_redirects",
            "max_response_bytes",
            "max_content_chars_per_request",
            "max_batch_content_chars",
        ):
            if getattr(self, field_name) < 1:
                msg = f"{field_name} must be at least 1"
                raise ValueError(msg)
        if self.max_parallel_fetches > self.max_requests_per_call:
            msg = "max_parallel_fetches must not exceed max_requests_per_call"
            raise ValueError(msg)
        if self.per_request_timeout_seconds <= 0:
            msg = "per_request_timeout_seconds must be positive"
            raise ValueError(msg)
        if self.max_retries < 0 or self.max_retries > DEFAULT_MAX_RETRIES:
            msg = "max_retries must be between 0 and 1"
            raise ValueError(msg)
        if self.max_content_chars_per_request < MIN_REQUEST_CONTENT_CHARS:
            msg = f"max_content_chars_per_request must be at least {MIN_REQUEST_CONTENT_CHARS}"
            raise ValueError(msg)
        if self.max_content_chars_per_request > DEFAULT_MAX_CONTENT_CHARS:
            msg = f"max_content_chars_per_request must not exceed {DEFAULT_MAX_CONTENT_CHARS}"
            raise ValueError(msg)
        if self.max_batch_content_chars < self.max_content_chars_per_request:
            msg = "max_batch_content_chars must not be shorter than max_content_chars_per_request"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class FetchWebContentRequest:
    """One canonical request for a known public URL."""

    url: str
    max_chars: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.strip():
            msg = "url must be a non-empty string"
            raise ValueError(msg)
        if self.max_chars is not None:
            if not isinstance(self.max_chars, int) or isinstance(self.max_chars, bool):
                msg = "max_chars must be an integer when provided"
                raise TypeError(msg)
            if not MIN_REQUEST_CONTENT_CHARS <= self.max_chars <= DEFAULT_MAX_CONTENT_CHARS:
                msg = f"max_chars must be between {MIN_REQUEST_CONTENT_CHARS} and {DEFAULT_MAX_CONTENT_CHARS}"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class FetchWebContentCommand:
    """Canonical ordered batch of public-web fetch requests."""

    requests: tuple[FetchWebContentRequest, ...]

    def __post_init__(self) -> None:
        if not self.requests:
            msg = "requests must not be empty"
            raise ValueError(msg)
        if len(self.requests) > DEFAULT_MAX_REQUESTS_PER_CALL:
            msg = f"requests must not exceed {DEFAULT_MAX_REQUESTS_PER_CALL} entries"
            raise ValueError(msg)
        if any(not isinstance(request, FetchWebContentRequest) for request in self.requests):
            msg = "requests must contain FetchWebContentRequest values"
            raise TypeError(msg)
        object.__setattr__(self, "requests", tuple(self.requests))


@dataclass(frozen=True, slots=True)
class FetchRedirect:
    """One validated HTTP redirect hop."""

    status: int
    from_url: str
    to_url: str

    def __post_init__(self) -> None:
        _validate_http_status(self.status)
        _validate_url_text(self.from_url, field_name="from_url")
        _validate_url_text(self.to_url, field_name="to_url")


@dataclass(frozen=True, slots=True)
class FetchError:
    """Safe structured error details for a fetch failure."""

    code: FetchErrorCode
    message: str = ""
    metadata: Mapping[str, SafeFetchMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.code, FetchErrorCode):
            msg = "code must be a FetchErrorCode"
            raise TypeError(msg)
        if not isinstance(self.message, str) or len(self.message) > MAX_ERROR_MESSAGE_CHARS:
            msg = "message must be a bounded string"
            raise ValueError(msg)
        _validate_safe_metadata(self.metadata)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcessedWebContent:
    """Application-owned normalized content produced from a successful response."""

    media_type: str
    content_format: FetchContentFormat
    content: str
    content_chars: int
    returned_chars: int
    truncated: bool
    parse_warning: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.media_type, str) or not self.media_type:
            msg = "media_type must be a non-empty string"
            raise ValueError(msg)
        if not isinstance(self.content_format, FetchContentFormat):
            msg = "content_format must be a FetchContentFormat"
            raise TypeError(msg)
        if not isinstance(self.content, str):
            msg = "content must be a string"
            raise TypeError(msg)
        if self.content_chars < 0 or self.returned_chars < 0:
            msg = "content sizes must not be negative"
            raise ValueError(msg)
        if self.returned_chars != len(self.content):
            msg = "returned_chars must equal the content length"
            raise ValueError(msg)
        if self.content_chars < self.returned_chars:
            msg = "content_chars must not be shorter than returned_chars"
            raise ValueError(msg)
        if not isinstance(self.truncated, bool):
            msg = "truncated must be a boolean"
            raise TypeError(msg)
        if self.parse_warning is not None and not isinstance(self.parse_warning, str):
            msg = "parse_warning must be a string when provided"
            raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class FetchSuccess:
    """Normalized successful public-web fetch result."""

    requested_url: str
    final_url: str
    status: int
    content_type: str
    media_type: str
    size_bytes: int
    content_format: FetchContentFormat
    content: str
    content_chars: int
    returned_chars: int
    truncated: bool
    redirects: tuple[FetchRedirect, ...] = field(default_factory=tuple)
    trust: str = TRUST_UNTRUSTED_WEB_CONTENT
    success: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        _validate_url_text(self.requested_url, field_name="requested_url")
        _validate_url_text(self.final_url, field_name="final_url")
        _validate_http_status(self.status)
        if not isinstance(self.content_type, str) or not self.content_type:
            msg = "content_type must be a non-empty string"
            raise ValueError(msg)
        if not isinstance(self.media_type, str) or not self.media_type:
            msg = "media_type must be a non-empty string"
            raise ValueError(msg)
        if not isinstance(self.content_format, FetchContentFormat):
            msg = "content_format must be a FetchContentFormat"
            raise TypeError(msg)
        if self.size_bytes < 0 or self.content_chars < 0 or self.returned_chars < 0:
            msg = "content sizes must not be negative"
            raise ValueError(msg)
        if self.content_chars != len(self.content):
            msg = "content_chars must equal the content length"
            raise ValueError(msg)
        if self.returned_chars != len(self.content):
            msg = "returned_chars must equal the returned content length"
            raise ValueError(msg)
        if not isinstance(self.truncated, bool):
            msg = "truncated must be a boolean"
            raise TypeError(msg)
        if self.trust != TRUST_UNTRUSTED_WEB_CONTENT:
            msg = "trust must identify untrusted web content"
            raise ValueError(msg)
        _validate_redirects(self.redirects)
        object.__setattr__(self, "redirects", tuple(self.redirects))


@dataclass(frozen=True, slots=True)
class FetchFailure:
    """Structured unsuccessful public-web fetch result retaining known metadata."""

    requested_url: str
    error: FetchError
    final_url: str | None = None
    status: int | None = None
    redirects: tuple[FetchRedirect, ...] = field(default_factory=tuple)
    trust: str = TRUST_UNTRUSTED_WEB_CONTENT
    success: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _validate_url_text(self.requested_url, field_name="requested_url")
        if not isinstance(self.error, FetchError):
            msg = "error must be a FetchError"
            raise TypeError(msg)
        if self.final_url is not None:
            _validate_url_text(self.final_url, field_name="final_url")
        if self.status is not None:
            _validate_http_status(self.status)
        if self.trust != TRUST_UNTRUSTED_WEB_CONTENT:
            msg = "trust must identify untrusted web content"
            raise ValueError(msg)
        _validate_redirects(self.redirects)
        object.__setattr__(self, "redirects", tuple(self.redirects))


type FetchResult = FetchSuccess | FetchFailure


@dataclass(frozen=True, slots=True)
class FetchWebContentResult:
    """Ordered results for one fetch-web-content invocation."""

    results: tuple[FetchResult, ...]
    batch_content_truncated: bool = False

    def __post_init__(self) -> None:
        if not self.results:
            msg = "results must not be empty"
            raise ValueError(msg)
        if any(not isinstance(result, FetchSuccess | FetchFailure) for result in self.results):
            msg = "results must contain fetch outcomes"
            raise TypeError(msg)
        if not isinstance(self.batch_content_truncated, bool):
            msg = "batch_content_truncated must be a boolean"
            raise TypeError(msg)
        object.__setattr__(self, "results", tuple(self.results))


@dataclass(frozen=True, slots=True)
class FetchAttemptSuccess:
    """Provider-neutral response captured from one already-validated fetch attempt."""

    final_url: str
    status: int
    content_type: str
    body: bytes
    redirects: tuple[FetchRedirect, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_url_text(self.final_url, field_name="final_url")
        _validate_http_status(self.status)
        if not isinstance(self.content_type, str):
            msg = "content_type must be a string"
            raise TypeError(msg)
        if not isinstance(self.body, bytes):
            msg = "body must be bytes"
            raise TypeError(msg)
        _validate_redirects(self.redirects)
        object.__setattr__(self, "redirects", tuple(self.redirects))


@dataclass(frozen=True, slots=True)
class FetchAttemptFailure:
    """Typed one-attempt failure, including retryable transport metadata."""

    error: FetchError
    retryable: bool = False
    retry_after_seconds: float | None = None
    final_url: str | None = None
    status: int | None = None
    redirects: tuple[FetchRedirect, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.error, FetchError):
            msg = "error must be a FetchError"
            raise TypeError(msg)
        if not isinstance(self.retryable, bool):
            msg = "retryable must be a boolean"
            raise TypeError(msg)
        if self.retry_after_seconds is not None:
            if not self.retryable:
                msg = "retry_after_seconds requires a retryable failure"
                raise ValueError(msg)
            if not 0 <= self.retry_after_seconds <= MAX_RETRY_AFTER_SECONDS:
                msg = f"retry_after_seconds must be between 0 and {MAX_RETRY_AFTER_SECONDS}"
                raise ValueError(msg)
        if self.final_url is not None:
            _validate_url_text(self.final_url, field_name="final_url")
        if self.status is not None:
            _validate_http_status(self.status)
        _validate_redirects(self.redirects)
        object.__setattr__(self, "redirects", tuple(self.redirects))


type FetchAttemptOutcome = FetchAttemptSuccess | FetchAttemptFailure


def _validate_http_status(status: int) -> None:
    if not isinstance(status, int) or isinstance(status, bool) or not MIN_HTTP_STATUS <= status <= MAX_HTTP_STATUS:
        msg = "status must be an HTTP status code"
        raise ValueError(msg)


def _validate_url_text(url: str, *, field_name: str) -> None:
    if not isinstance(url, str) or not url:
        msg = f"{field_name} must be a non-empty string"
        raise ValueError(msg)


def _validate_redirects(redirects: tuple[FetchRedirect, ...]) -> None:
    if any(not isinstance(redirect, FetchRedirect) for redirect in redirects):
        msg = "redirects must contain FetchRedirect values"
        raise TypeError(msg)


def _validate_safe_metadata(metadata: Mapping[str, SafeFetchMetadataValue]) -> None:
    for key, value in metadata.items():
        if not isinstance(key, str) or not key:
            msg = "error metadata keys must be non-empty strings"
            raise ValueError(msg)
        if not isinstance(value, str | int | float | bool | type(None)):
            msg = "error metadata values must be scalar and safe"
            raise TypeError(msg)
