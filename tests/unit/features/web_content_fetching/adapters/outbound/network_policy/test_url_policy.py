"""Tests for pure public-web URL validation."""

import pytest

from fabrica.features.web_content_fetching.adapters.outbound.network_policy import ValidatedWebUrl, validate_web_url
from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode


@pytest.mark.parametrize(
    ("url", "is_redirect", "error_code"),
    [
        ("http://example.com", False, FetchErrorCode.UNSUPPORTED_PROTOCOL),
        ("http://example.com", True, FetchErrorCode.INSECURE_REDIRECT),
        ("ftp://example.com", False, FetchErrorCode.UNSUPPORTED_PROTOCOL),
        ("https://user:password@example.com", False, FetchErrorCode.URL_CREDENTIALS_NOT_ALLOWED),
        ("https:///path", False, FetchErrorCode.INVALID_URL),
        ("https://example.com:invalid", False, FetchErrorCode.INVALID_URL),
        (" https://example.com", False, FetchErrorCode.INVALID_URL),
    ],
)
def test_validate_web_url_rejects_unsafe_or_malformed_urls(
    url: str,
    is_redirect: object,
    error_code: FetchErrorCode,
) -> None:
    assert isinstance(is_redirect, bool)
    result = validate_web_url(url, is_redirect=is_redirect)

    assert isinstance(result, FetchError)
    assert result.code is error_code


@pytest.mark.parametrize(
    ("url", "normalized", "hostname"),
    [
        ("https://Example.COM/docs", "https://example.com/docs", "example.com"),
        ("https://bücher.example/docs", "https://xn--bcher-kva.example/docs", "xn--bcher-kva.example"),
        ("https://127.0.0.1/docs", "https://127.0.0.1/docs", "127.0.0.1"),
        ("https://[2001:4860:4860::8888]/dns", "https://[2001:4860:4860::8888]/dns", "2001:4860:4860::8888"),
    ],
)
def test_validate_web_url_normalizes_supported_hosts(url: str, normalized: str, hostname: str) -> None:
    result = validate_web_url(url)

    assert result == ValidatedWebUrl(url=normalized, hostname=hostname)
