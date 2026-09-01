"""Tests for public web-content fetching application DTOs."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

from fabrica.features.web_content_fetching.application.dtos import (
    DEFAULT_MAX_BATCH_CONTENT_CHARS,
    DEFAULT_MAX_CONTENT_CHARS,
    DEFAULT_MAX_PARALLEL_FETCHES,
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_MAX_REQUESTS_PER_CALL,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_MAX_RETRIES,
    DEFAULT_PER_REQUEST_TIMEOUT_SECONDS,
    TRUST_UNTRUSTED_WEB_CONTENT,
    FetchAttemptFailure,
    FetchAttemptSuccess,
    FetchContentFormat,
    FetchError,
    FetchErrorCode,
    FetchFailure,
    FetchRedirect,
    FetchSuccess,
    FetchWebContentCommand,
    FetchWebContentLimits,
    FetchWebContentRequest,
    FetchWebContentResult,
)


def test_fetch_limits_default_to_the_accepted_version_one_bounds() -> None:
    assert FetchWebContentLimits() == FetchWebContentLimits(
        max_requests_per_call=DEFAULT_MAX_REQUESTS_PER_CALL,
        max_parallel_fetches=DEFAULT_MAX_PARALLEL_FETCHES,
        per_request_timeout_seconds=DEFAULT_PER_REQUEST_TIMEOUT_SECONDS,
        max_retries=DEFAULT_MAX_RETRIES,
        max_redirects=DEFAULT_MAX_REDIRECTS,
        max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
        max_content_chars_per_request=DEFAULT_MAX_CONTENT_CHARS,
        max_batch_content_chars=DEFAULT_MAX_BATCH_CONTENT_CHARS,
    )


def _too_many_requests_command() -> FetchWebContentCommand:
    return FetchWebContentCommand(tuple(FetchWebContentRequest(f"https://{index}.example") for index in range(9)))


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: FetchWebContentLimits(max_parallel_fetches=9), "must not exceed"),
        (lambda: FetchWebContentLimits(per_request_timeout_seconds=0), "positive"),
        (lambda: FetchWebContentLimits(max_retries=2), "between 0 and 1"),
        (lambda: FetchWebContentLimits(max_content_chars_per_request=999), "at least 1000"),
        (lambda: FetchWebContentLimits(max_batch_content_chars=47_999), "must not be shorter"),
        (lambda: FetchWebContentRequest("https://example.com", max_chars=999), "between 1000 and 48000"),
        (lambda: FetchWebContentRequest("https://example.com", max_chars=True), "integer"),
        (lambda: FetchWebContentCommand(()), "must not be empty"),
        (_too_many_requests_command, "must not exceed"),
    ],
)
def test_fetch_input_dtos_reject_invalid_bounds_and_shapes(factory: Callable[[], object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        factory()


def test_success_and_failure_results_retain_contract_metadata_and_trust() -> None:
    redirect = FetchRedirect(301, "https://example.com", "https://www.example.com")
    success = FetchSuccess(
        requested_url="https://example.com",
        final_url="https://www.example.com",
        status=204,
        content_type="text/plain",
        media_type="text/plain",
        size_bytes=0,
        content_format=FetchContentFormat.TEXT,
        content="",
        content_chars=0,
        returned_chars=0,
        truncated=False,
        redirects=(redirect,),
    )
    failure = FetchFailure(
        requested_url="https://example.com",
        final_url="https://www.example.com",
        status=503,
        redirects=(redirect,),
        error=FetchError(FetchErrorCode.HTTP_ERROR, "HTTP 503 Service Unavailable"),
    )
    result = FetchWebContentResult((success, failure))

    assert success.success is True
    assert failure.success is False
    assert result.results == (success, failure)
    assert all(item.trust == TRUST_UNTRUSTED_WEB_CONTENT for item in result.results)
    with pytest.raises(FrozenInstanceError):
        _set_frozen_field(success, "status", 200)


def test_fetch_result_dtos_reject_impossible_content_and_retry_states() -> None:
    with pytest.raises(ValueError, match="content_chars"):
        FetchSuccess(
            requested_url="https://example.com",
            final_url="https://example.com",
            status=200,
            content_type="text/plain",
            media_type="text/plain",
            size_bytes=3,
            content_format=FetchContentFormat.TEXT,
            content="one",
            content_chars=2,
            returned_chars=3,
            truncated=False,
        )
    with pytest.raises(ValueError, match="requires a retryable"):
        FetchAttemptFailure(FetchError(FetchErrorCode.CONNECTION_FAILED), retry_after_seconds=1)
    with pytest.raises(ValueError, match="between 0 and 60"):
        FetchAttemptFailure(FetchError(FetchErrorCode.HTTP_ERROR), retryable=True, retry_after_seconds=61)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: FetchWebContentLimits(max_requests_per_call=0), "at least 1"),
        (lambda: FetchWebContentLimits(max_redirects=0), "at least 1"),
        (lambda: FetchWebContentLimits(max_content_chars_per_request=48_001), "must not exceed"),
        (lambda: FetchWebContentRequest(" "), "non-empty"),
        (
            lambda: FetchWebContentCommand(
                cast("tuple[FetchWebContentRequest, ...]", (FetchWebContentRequest("https://example.com"), "invalid"))
            ),
            "must contain",
        ),
        (lambda: FetchRedirect(99, "https://example.com", "https://next.example"), "HTTP status"),
        (lambda: FetchRedirect(301, "", "https://next.example"), "from_url"),
        (lambda: FetchError(FetchErrorCode.DNS_FAILED, "x" * 1_001), "bounded"),
        (lambda: FetchError(FetchErrorCode.DNS_FAILED, metadata={"": "value"}), "non-empty"),
        (
            lambda: FetchError(
                FetchErrorCode.DNS_FAILED,
                metadata=cast("dict[str, str | int | float | bool | None]", {"detail": object()}),
            ),
            "scalar and safe",
        ),
    ],
)
def test_fetch_request_and_metadata_dtos_reject_invalid_values(factory: Callable[[], object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        factory()


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: _success(content_chars=3, returned_chars=2), "returned_chars"),
        (lambda: _success(size_bytes=-1), "must not be negative"),
        (lambda: replace(_success(), truncated=cast("bool", 1)), "boolean"),
        (lambda: _success(trust="trusted"), "untrusted"),
        (lambda: replace(_success(), redirects=cast("tuple[FetchRedirect, ...]", ("invalid",))), "FetchRedirect"),
        (lambda: FetchFailure("https://example.com", FetchError(FetchErrorCode.DNS_FAILED), status=600), "HTTP status"),
        (
            lambda: FetchFailure("https://example.com", FetchError(FetchErrorCode.DNS_FAILED), trust="trusted"),
            "untrusted",
        ),
        (lambda: FetchWebContentResult(()), "must not be empty"),
        (
            lambda: FetchWebContentResult(cast("tuple[FetchSuccess | FetchFailure, ...]", ("invalid",))),
            "fetch outcomes",
        ),
        (lambda: FetchWebContentResult((_success(),), batch_content_truncated=cast("bool", 1)), "boolean"),
    ],
)
def test_fetch_result_dtos_reject_inconsistent_result_states(factory: Callable[[], object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        factory()


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: FetchAttemptSuccess("https://example.com", 200, "text/plain", cast("bytes", "not-bytes")),
            "body must be bytes",
        ),
        (lambda: FetchAttemptSuccess("", 200, "text/plain", b"body"), "final_url"),
        (lambda: FetchAttemptFailure(cast("FetchError", "invalid")), "FetchError"),
        (
            lambda: FetchAttemptFailure(FetchError(FetchErrorCode.CONNECTION_FAILED), retryable=cast("bool", 1)),
            "boolean",
        ),
        (
            lambda: FetchAttemptFailure(FetchError(FetchErrorCode.CONNECTION_FAILED), retryable=True, final_url=""),
            "final_url",
        ),
        (lambda: FetchAttemptFailure(FetchError(FetchErrorCode.HTTP_ERROR), status=99), "HTTP status"),
    ],
)
def test_fetch_attempt_dtos_reject_invalid_transport_outcomes(factory: Callable[[], object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        factory()


def _success(**overrides: int | str) -> FetchSuccess:
    success = FetchSuccess(
        requested_url="https://example.com",
        final_url="https://example.com",
        status=200,
        content_type="text/plain",
        media_type="text/plain",
        size_bytes=3,
        content_format=FetchContentFormat.TEXT,
        content="one",
        content_chars=3,
        returned_chars=3,
        truncated=False,
    )
    return replace(success, **overrides)


def test_fetch_error_taxonomy_covers_the_accepted_failure_contract() -> None:
    assert {code.value for code in FetchErrorCode} == {
        "INVALID_INPUT",
        "INVALID_URL",
        "UNSUPPORTED_PROTOCOL",
        "INSECURE_REDIRECT",
        "URL_CREDENTIALS_NOT_ALLOWED",
        "DNS_FAILED",
        "DESTINATION_NOT_ALLOWED",
        "TOO_MANY_REDIRECTS",
        "INVALID_REDIRECT",
        "CONNECTION_FAILED",
        "TLS_ERROR",
        "FETCH_TIMEOUT",
        "FETCH_CANCELLED",
        "HTTP_ERROR",
        "RESPONSE_TOO_LARGE",
        "UNSUPPORTED_CONTENT_TYPE",
        "UNSUPPORTED_ENCODING",
        "INVALID_JSON",
        "CONTENT_EXTRACTION_FAILED",
        "INTERNAL_FETCH_ERROR",
        "PUBLIC_WEB_DISABLED",
    }


def _set_frozen_field(instance: object, field_name: str, value: object) -> None:
    """Attempt ordinary mutation through a dynamic test boundary."""
    setattr(instance, field_name, value)
