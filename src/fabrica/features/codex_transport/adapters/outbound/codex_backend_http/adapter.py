"""HTTP implementation and request building for Codex backend outbound ports."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

import httpx

from fabrica.adapters.outbound.httpx_client import (
    HttpxRequest,
    HttpxRetryExecutor,
    RetryDiagnostics,
    RetryOutcome,
    RetryPolicy,
    diagnostics_metadata,
)
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.response_mapping import (
    CodexBackendResponse,
    CodexUsageResponse,
    map_codex_backend_response,
    map_codex_backend_transport_error,
    map_codex_usage_response,
    map_codex_usage_transport_error,
)
from fabrica.features.codex_transport.adapters.outbound.redaction import redact_metadata
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportObservation,
    CodexTransportResult,
    CodexUsageProbeCommand,
    CodexUsageResult,
)

DEFAULT_CODEX_BACKEND_BASE_URL = "https://chatgpt.com/backend-api/"
DEFAULT_CODEX_BACKEND_PATH = "codex/responses"
DEFAULT_CODEX_USAGE_PATH = "api/codex/usage"
DEFAULT_CODEX_MODEL = "gpt-5.6-sol"
DEFAULT_CODEX_PRODUCT_SKU = "codex"
DEFAULT_CODEX_COMPLETION_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
DEFAULT_CODEX_USAGE_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
DEFAULT_CODEX_COMPLETION_RETRY_POLICY = RetryPolicy(
    retryable_status_codes=frozenset({429}),
    retryable_exception_types=(),
    total_budget_seconds=180.0,
)
DEFAULT_CODEX_USAGE_RETRY_POLICY = RetryPolicy(total_budget_seconds=30.0)


@dataclass(frozen=True, slots=True)
class CodexHttpRequestExecution:
    """Parameters needed to execute one Codex HTTP request."""

    method: str
    url: str
    headers: Mapping[str, str]
    json_payload: Mapping[str, object] | None
    timeout: float | httpx.Timeout
    policy: RetryPolicy


@dataclass(frozen=True, slots=True)
class CodexBackendRequestSettings:
    """Adapter-owned settings for stream-backed completion requests.

    ``base_url`` and ``path`` identify the Codex responses endpoint, ``model``
    and ``product_sku`` are sent on every completion request, and
    ``reasoning_effort`` is omitted unless explicitly configured.
    """

    base_url: str = DEFAULT_CODEX_BACKEND_BASE_URL
    path: str = DEFAULT_CODEX_BACKEND_PATH
    model: str = DEFAULT_CODEX_MODEL
    product_sku: str = DEFAULT_CODEX_PRODUCT_SKU
    reasoning_effort: str | None = None


@dataclass(frozen=True, slots=True)
class CodexUsageRequestSettings:
    """Adapter-owned settings for Codex usage evidence requests."""

    base_url: str = DEFAULT_CODEX_BACKEND_BASE_URL
    usage_path: str = DEFAULT_CODEX_USAGE_PATH


@dataclass(frozen=True, slots=True)
class CodexBackendRequest:
    """Adapter-owned representation of a stream-backed completion request."""

    url: str
    headers: Mapping[str, str]
    json_payload: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))
        object.__setattr__(self, "json_payload", MappingProxyType(dict(self.json_payload)))

    def redacted_observation(self) -> CodexTransportObservation:
        """Return bounded, secret-safe diagnostics for the built request."""
        redacted_headers = redact_metadata(self.headers)
        return CodexTransportObservation(
            message="built Codex backend request",
            metadata={
                "url": self.url,
                "authorization": str(redacted_headers.get("Authorization")),
                "account_header": str(redacted_headers.get("ChatGPT-Account-ID")),
                "header_count": len(self.headers),
                "payload_shape": "responses_streaming",
                "stream": self.json_payload.get("stream") is True,
            },
        )


@dataclass(frozen=True, slots=True)
class CodexUsageRequest:
    """Adapter-owned representation of a Codex usage evidence HTTP request.

    ``include_rate_limit_reset`` is an application observation preference. The
    current upstream endpoint exposes reset evidence in safe response headers
    when available; no additional request parameter is known for this flag.
    """

    url: str
    headers: Mapping[str, str]
    include_rate_limit_reset: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))

    def redacted_observation(self) -> CodexTransportObservation:
        """Return bounded, secret-safe diagnostics for the usage request."""
        redacted_headers = redact_metadata(self.headers)
        return CodexTransportObservation(
            message="built Codex usage evidence request",
            metadata={
                "url": self.url,
                "authorization": str(redacted_headers.get("Authorization")),
                "account_header": str(redacted_headers.get("ChatGPT-Account-ID")),
                "header_count": len(self.headers),
                "include_rate_limit_reset": self.include_rate_limit_reset,
            },
        )


def build_codex_backend_request(
    *,
    command: CodexCompletionCommand,
    credentials: CodexCredentials,
    settings: CodexBackendRequestSettings | None = None,
) -> CodexBackendRequest:
    """Build the current best-known stream-backed Codex completion request."""
    request_settings = settings or CodexBackendRequestSettings()
    json_payload: dict[str, object] = {
        "model": request_settings.model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": command.prompt},
                ],
            }
        ],
        "stream": True,
        "store": False,
    }
    if request_settings.reasoning_effort is not None:
        json_payload["reasoning"] = {"effort": request_settings.reasoning_effort}

    return CodexBackendRequest(
        url=_join_url(base_url=request_settings.base_url, path=request_settings.path),
        headers={
            "Authorization": f"Bearer {credentials.access_token}",
            "ChatGPT-Account-ID": credentials.account_id,
            "Content-Type": "application/json",
            "OAI-Product-Sku": request_settings.product_sku,
        },
        json_payload=json_payload,
    )


def build_codex_usage_request(
    *,
    command: CodexUsageProbeCommand,
    credentials: CodexCredentials,
    settings: CodexUsageRequestSettings | None = None,
) -> CodexUsageRequest:
    """Build the current best-known Codex usage evidence request."""
    request_settings = settings or CodexUsageRequestSettings()
    return CodexUsageRequest(
        url=_join_url(base_url=request_settings.base_url, path=request_settings.usage_path),
        headers={
            "Authorization": f"Bearer {credentials.access_token}",
            "ChatGPT-Account-ID": credentials.account_id,
            "Content-Type": "application/json",
        },
        include_rate_limit_reset=command.include_rate_limit_reset,
    )


@dataclass(frozen=True, slots=True)
class CodexBackendHttpAdapter:
    """Execute Codex backend calls through injected or internally owned HTTP clients.

    The completion/probe endpoint currently uses the stream-backed Codex
    responses wire shape, but this adapter consumes the HTTP response fully and
    returns one normalized application result. HTTP client exceptions are
    translated into secret-safe result DTOs instead of escaping through the
    outbound port boundary.
    """

    request_settings: CodexBackendRequestSettings | None = None
    usage_request_settings: CodexUsageRequestSettings | None = None
    completion_timeout: float | httpx.Timeout = field(default_factory=lambda: DEFAULT_CODEX_COMPLETION_TIMEOUT)
    usage_timeout: float | httpx.Timeout = field(default_factory=lambda: DEFAULT_CODEX_USAGE_TIMEOUT)
    completion_retry_policy: RetryPolicy = DEFAULT_CODEX_COMPLETION_RETRY_POLICY
    usage_retry_policy: RetryPolicy = DEFAULT_CODEX_USAGE_RETRY_POLICY
    retry_executor: HttpxRetryExecutor = field(default_factory=HttpxRetryExecutor)
    client: httpx.Client | None = None

    def complete(
        self,
        command: CodexCompletionCommand,
        credentials: CodexCredentials,
    ) -> CodexTransportResult:
        """Execute one Codex completion and return a normalized result."""
        request = build_codex_backend_request(
            command=command,
            credentials=credentials,
            settings=self.request_settings,
        )
        try:
            outcome = self._post(request)
        except httpx.HTTPError as err:
            return map_codex_backend_transport_error(err)
        if outcome.exception is not None:
            return _with_retry_observation(
                map_codex_backend_transport_error(outcome.exception),
                outcome.diagnostics,
            )
        response = outcome.response
        if response is None:
            return _with_retry_observation(
                map_codex_backend_transport_error(httpx.TransportError("HTTP request failed without a response")),
                outcome.diagnostics,
            )

        return _with_retry_observation(
            map_codex_backend_response(
                CodexBackendResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    json_body=_safe_json_body(response),
                )
            ),
            outcome.diagnostics,
        )

    def _post(self, request: CodexBackendRequest) -> RetryOutcome:
        return self._request(
            execution=CodexHttpRequestExecution(
                method="POST",
                url=request.url,
                headers=request.headers,
                json_payload=request.json_payload,
                timeout=self.completion_timeout,
                policy=self.completion_retry_policy,
            ),
        )

    def _get(self, request: CodexUsageRequest) -> RetryOutcome:
        return self._request(
            execution=CodexHttpRequestExecution(
                method="GET",
                url=request.url,
                headers=request.headers,
                json_payload=None,
                timeout=self.usage_timeout,
                policy=self.usage_retry_policy,
            ),
        )

    def _request(
        self,
        *,
        execution: CodexHttpRequestExecution,
    ) -> RetryOutcome:
        if self.client is not None:
            return self.retry_executor.request(
                client=self.client,
                request=HttpxRequest(
                    method=execution.method,
                    url=execution.url,
                    headers=execution.headers,
                    json=execution.json_payload,
                    timeout=execution.timeout,
                ),
                policy=execution.policy,
            )
        with httpx.Client() as client:
            return self.retry_executor.request(
                client=client,
                request=HttpxRequest(
                    method=execution.method,
                    url=execution.url,
                    headers=execution.headers,
                    json=execution.json_payload,
                    timeout=execution.timeout,
                ),
                policy=execution.policy,
            )

    def fetch_usage(
        self,
        command: CodexUsageProbeCommand,
        credentials: CodexCredentials,
    ) -> CodexUsageResult:
        """Fetch Codex usage and quota evidence via HTTP."""
        request = build_codex_usage_request(
            credentials=credentials,
            settings=self.usage_request_settings,
            command=command,
        )
        try:
            outcome = self._get(request)
        except httpx.HTTPError as err:
            return map_codex_usage_transport_error(err)
        if outcome.exception is not None:
            return _with_usage_retry_observation(
                map_codex_usage_transport_error(outcome.exception),
                outcome.diagnostics,
            )
        response = outcome.response
        if response is None:
            return _with_usage_retry_observation(
                map_codex_usage_transport_error(httpx.TransportError("HTTP request failed without a response")),
                outcome.diagnostics,
            )
        return _with_usage_retry_observation(
            map_codex_usage_response(
                CodexUsageResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    json_body=_safe_json_body(response),
                )
            ),
            outcome.diagnostics,
        )


def _with_retry_observation(
    result: CodexTransportResult,
    diagnostics: RetryDiagnostics,
) -> CodexTransportResult:
    return replace(
        result,
        observations=(*result.observations, _retry_observation(diagnostics)),
    )


def _with_usage_retry_observation(
    result: CodexUsageResult,
    diagnostics: RetryDiagnostics,
) -> CodexUsageResult:
    return replace(
        result,
        observations=(*result.observations, _retry_observation(diagnostics)),
    )


def _retry_observation(diagnostics: RetryDiagnostics) -> CodexTransportObservation:
    return CodexTransportObservation(
        message="HTTP retry policy completed",
        metadata=diagnostics_metadata(diagnostics),
    )


def _safe_json_body(response: httpx.Response) -> object:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return response.text
    try:
        return response.json()
    except ValueError:
        return response.text


def _join_url(*, base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
