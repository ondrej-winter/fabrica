"""HTTPX implementation of one policy-validated public-web fetch attempt."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx

from fabrica.features.web_content_fetching.adapters.outbound.network_policy import (
    ValidatedWebUrl,
    validate_public_destination,
    validate_web_url,
)
from fabrica.features.web_content_fetching.application.dtos import (
    FetchAttemptFailure,
    FetchAttemptOutcome,
    FetchAttemptSuccess,
    FetchError,
    FetchErrorCode,
    FetchRedirect,
    FetchWebContentRequest,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext, PublicDnsResolver

_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_RETRYABLE_STATUS_CODES = frozenset({408, 429, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class _RequestState:
    """Current validated location and redirect history for one fetch attempt."""

    url: ValidatedWebUrl
    redirects: tuple[FetchRedirect, ...] = ()


class HttpxWebContentAttemptFetcher:
    """Retrieve one public HTTPS resource with explicit policy checks per redirect hop."""

    def __init__(
        self,
        *,
        resolver: PublicDnsResolver,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._resolver = resolver
        self._client_factory = client_factory if client_factory is not None else httpx.AsyncClient
        self._headers = dict(headers or {})

    async def fetch_attempt(
        self,
        request: FetchWebContentRequest,
        context: FetchWebContentContext,
    ) -> FetchAttemptOutcome:
        """Fetch one request, returning response bytes or a stable typed failure."""
        initial_failure = _preflight_failure(context)
        if initial_failure is not None:
            return initial_failure
        state = _initial_state(request)
        if isinstance(state, FetchAttemptFailure):
            return state
        try:
            async with self._client_factory() as client:
                return await self._fetch_chain(client, state, context)
        except asyncio.CancelledError:
            return _state_failure(FetchErrorCode.FETCH_CANCELLED, "Fetch was cancelled", state)
        except httpx.HTTPError as err:
            return _httpx_failure(err, state)

    async def _fetch_chain(
        self,
        client: httpx.AsyncClient,
        state: _RequestState,
        context: FetchWebContentContext,
    ) -> FetchAttemptOutcome:
        """Fetch sequential redirect hops until a terminal typed outcome occurs."""
        while True:
            destination_failure = await _destination_failure(state, self._resolver, context)
            if destination_failure is not None:
                return destination_failure
            outcome = await _fetch_response(client, state, context, self._headers)
            if isinstance(outcome, FetchAttemptFailure | FetchAttemptSuccess):
                return outcome
            next_state = _next_redirect_state(state, outcome[0], outcome[1], context.limits.max_redirects)
            if isinstance(next_state, FetchAttemptFailure):
                return next_state
            state = next_state


def _preflight_failure(context: FetchWebContentContext) -> FetchAttemptFailure | None:
    """Return a terminal failure before URL, DNS, or HTTP work when required."""
    if context.cancellation.is_cancelled:
        return FetchAttemptFailure(FetchError(FetchErrorCode.FETCH_CANCELLED, "Fetch was cancelled"))
    if _deadline_expired(context):
        return FetchAttemptFailure(FetchError(FetchErrorCode.FETCH_TIMEOUT, "Fetch deadline expired"))
    return None


def _initial_state(request: FetchWebContentRequest) -> _RequestState | FetchAttemptFailure:
    """Validate the requested URL before any network-related operation."""
    url = validate_web_url(request.url)
    return FetchAttemptFailure(url) if isinstance(url, FetchError) else _RequestState(url)


async def _destination_failure(
    state: _RequestState,
    resolver: PublicDnsResolver,
    context: FetchWebContentContext,
) -> FetchAttemptFailure | None:
    """Validate cancellation, deadline, DNS, and destination policy for one hop."""
    preflight_failure = _preflight_failure(context)
    if preflight_failure is not None:
        return _state_failure(preflight_failure.error.code, preflight_failure.error.message, state)
    destination = await validate_public_destination(state.url, resolver=resolver, context=context)
    if isinstance(destination, FetchError):
        return FetchAttemptFailure(destination, final_url=state.url.url, redirects=state.redirects)
    return None


async def _fetch_response(
    client: httpx.AsyncClient,
    state: _RequestState,
    context: FetchWebContentContext,
    headers: Mapping[str, str],
) -> FetchAttemptSuccess | FetchAttemptFailure | tuple[int, str | None]:
    """Stream one response and close it before returning a terminal outcome."""
    try:
        async with client.stream(
            "GET",
            state.url.url,
            headers=dict(headers),
            follow_redirects=False,
            timeout=_remaining_timeout(context),
        ) as response:
            return await _response_outcome(response, state, context)
    except httpx.TimeoutException:
        return _state_failure(FetchErrorCode.FETCH_TIMEOUT, "Fetch timed out", state)
    except httpx.ConnectError:
        return _state_failure(FetchErrorCode.CONNECTION_FAILED, "Connection failed", state, retryable=True)
    except httpx.TransportError:
        return _state_failure(FetchErrorCode.CONNECTION_FAILED, "HTTP transport failed", state, retryable=True)


async def _response_outcome(
    response: httpx.Response,
    state: _RequestState,
    context: FetchWebContentContext,
) -> FetchAttemptSuccess | FetchAttemptFailure | tuple[int, str | None]:
    """Convert an open response into a redirect or typed terminal outcome."""
    if response.status_code in _REDIRECT_STATUS_CODES:
        return response.status_code, response.headers.get("location")
    if not response.is_success:
        return _state_failure(
            FetchErrorCode.HTTP_ERROR,
            "HTTP request returned an error status",
            state,
            status=response.status_code,
            retryable=response.status_code in _RETRYABLE_STATUS_CODES,
        )
    if _declared_size_exceeds_limit(response, context.limits.max_response_bytes):
        return _state_failure(
            FetchErrorCode.RESPONSE_TOO_LARGE,
            "Response body exceeds the configured size limit",
            state,
            status=response.status_code,
        )
    body = await _read_body(response, context)
    if isinstance(body, FetchError):
        return _state_failure(body.code, body.message, state, status=response.status_code)
    return FetchAttemptSuccess(
        final_url=state.url.url,
        status=response.status_code,
        content_type=response.headers.get("content-type", "application/octet-stream"),
        body=body,
        redirects=state.redirects,
    )


def _next_redirect_state(
    state: _RequestState,
    status: int,
    location: str | None,
    max_redirects: int,
) -> _RequestState | FetchAttemptFailure:
    """Resolve, validate, and record the next redirect target without I/O."""
    if len(state.redirects) >= max_redirects:
        return _state_failure(FetchErrorCode.TOO_MANY_REDIRECTS, "Redirect limit exceeded", state, status=status)
    if location is None:
        return _state_failure(
            FetchErrorCode.INVALID_REDIRECT,
            "Redirect response did not include a Location header",
            state,
            status=status,
        )
    target = validate_web_url(urljoin(state.url.url, location), is_redirect=True)
    if isinstance(target, FetchError):
        return FetchAttemptFailure(target, final_url=state.url.url, status=status, redirects=state.redirects)
    redirect = FetchRedirect(status, state.url.url, target.url)
    return _RequestState(target, (*state.redirects, redirect))


async def _read_body(response: httpx.Response, context: FetchWebContentContext) -> bytes | FetchError:
    """Read decoded body bytes, enforcing cancellation, deadline, and size bounds."""
    chunks: list[bytes] = []
    received_bytes = 0
    async for chunk in response.aiter_bytes():
        preflight_failure = _preflight_failure(context)
        if preflight_failure is not None:
            return preflight_failure.error
        received_bytes += len(chunk)
        if received_bytes > context.limits.max_response_bytes:
            return FetchError(FetchErrorCode.RESPONSE_TOO_LARGE, "Response body exceeds the configured size limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _declared_size_exceeds_limit(response: httpx.Response, limit: int) -> bool:
    """Return whether a valid declared body size already exceeds the configured limit."""
    value = response.headers.get("content-length")
    try:
        return value is not None and int(value) > limit
    except ValueError:
        return False


def _remaining_timeout(context: FetchWebContentContext) -> float:
    """Return the configured timeout bounded by the host deadline when present."""
    if context.deadline_at is None:
        return context.limits.per_request_timeout_seconds
    return max((context.deadline_at - datetime.now(UTC)).total_seconds(), 0.0)


def _deadline_expired(context: FetchWebContentContext) -> bool:
    """Return whether the timezone-aware host deadline has elapsed."""
    return context.deadline_at is not None and datetime.now(UTC) >= context.deadline_at


def _state_failure(
    code: FetchErrorCode,
    message: str,
    state: _RequestState,
    *,
    status: int | None = None,
    retryable: bool = False,
) -> FetchAttemptFailure:
    """Create a failure that retains validated URL and redirect metadata."""
    return FetchAttemptFailure(
        error=FetchError(code, message),
        retryable=retryable,
        final_url=state.url.url,
        status=status,
        redirects=state.redirects,
    )


def _httpx_failure(error: httpx.HTTPError, state: _RequestState) -> FetchAttemptFailure:
    """Map an HTTPX exception to a stable transport failure without provider detail."""
    if isinstance(error, httpx.TimeoutException):
        return _state_failure(FetchErrorCode.FETCH_TIMEOUT, "Fetch timed out", state)
    if isinstance(error, httpx.ConnectError):
        return _state_failure(FetchErrorCode.CONNECTION_FAILED, "Connection failed", state, retryable=True)
    return _state_failure(FetchErrorCode.CONNECTION_FAILED, "HTTP transport failed", state, retryable=True)
