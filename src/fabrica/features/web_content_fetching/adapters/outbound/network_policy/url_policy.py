"""Syntax and protocol validation for public web fetch destinations."""

from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode


@dataclass(frozen=True, slots=True)
class ValidatedWebUrl:
    """A normalized HTTPS URL that is safe to pass to destination validation."""

    url: str
    hostname: str


def validate_web_url(url: str, *, is_redirect: bool = False) -> ValidatedWebUrl | FetchError:
    """Validate and normalize one initial URL or redirect destination without I/O."""
    if not isinstance(url, str) or not url or url != url.strip() or any(character.isspace() for character in url):
        return _error(FetchErrorCode.INVALID_URL, "URL must be a non-empty URL without whitespace")
    parsed = _parse_url(url)
    if isinstance(parsed, FetchError):
        return parsed
    hostname = _validated_hostname(parsed, is_redirect=is_redirect)
    if isinstance(hostname, FetchError):
        return hostname
    normalized_netloc = _normalized_netloc(hostname, parsed.port)
    normalized = urlunsplit(("https", normalized_netloc, parsed.path or "/", parsed.query, parsed.fragment))
    return ValidatedWebUrl(url=normalized, hostname=hostname)


def _parse_url(url: str) -> SplitResult | FetchError:
    """Parse a URL while translating malformed port syntax to a stable error."""
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError:
        return _error(FetchErrorCode.INVALID_URL, "URL is malformed")
    return parsed


def _validated_hostname(parsed: SplitResult, *, is_redirect: bool) -> str | FetchError:
    """Validate protocol and credentials, then return normalized hostname text."""
    if parsed.scheme.lower() != "https":
        return _error(_protocol_error_code(parsed.scheme, is_redirect=is_redirect), "Only HTTPS URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        return _error(FetchErrorCode.URL_CREDENTIALS_NOT_ALLOWED, "URL credentials are not allowed")
    if parsed.hostname is None:
        return _error(FetchErrorCode.INVALID_URL, "URL must include a hostname")
    try:
        return parsed.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return _error(FetchErrorCode.INVALID_URL, "URL hostname is invalid")


def _protocol_error_code(scheme: str, *, is_redirect: bool) -> FetchErrorCode:
    """Return the accepted protocol error for initial URLs and redirect targets."""
    return (
        FetchErrorCode.INSECURE_REDIRECT
        if is_redirect and scheme.lower() == "http"
        else FetchErrorCode.UNSUPPORTED_PROTOCOL
    )


def _normalized_netloc(hostname: str, port: int | None) -> str:
    """Return a canonical authority from a parsed URL and normalized hostname."""
    rendered_host = f"[{hostname}]" if ":" in hostname else hostname
    return rendered_host if port is None else f"{rendered_host}:{port}"


def _error(code: FetchErrorCode, message: str) -> FetchError:
    """Create one safe policy-validation error."""
    return FetchError(code=code, message=message)


__all__ = ["ValidatedWebUrl", "validate_web_url"]
