"""HTTP implementation of the Codex backend outbound ports."""

from dataclasses import dataclass

import httpx

from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.request_builder import (
    CodexBackendRequest,
    CodexBackendRequestSettings,
    CodexUsageRequest,
    CodexUsageRequestSettings,
    build_codex_backend_request,
    build_codex_usage_request,
)
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.response_mapper import (
    CodexBackendResponse,
    CodexUsageResponse,
    map_codex_backend_response,
    map_codex_backend_transport_error,
    map_codex_usage_response,
    map_codex_usage_transport_error,
)
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportResult,
    CodexUsageProbeCommand,
    CodexUsageResult,
)

DEFAULT_CODEX_BACKEND_TIMEOUT_SECONDS = 30.0


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
    timeout: float | httpx.Timeout = DEFAULT_CODEX_BACKEND_TIMEOUT_SECONDS
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
            response = self._post(request)
        except httpx.HTTPError as err:
            return map_codex_backend_transport_error(err)

        return map_codex_backend_response(
            CodexBackendResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                json_body=_safe_json_body(response),
            )
        )

    def fetch_usage(
        self,
        command: CodexUsageProbeCommand,
        credentials: CodexCredentials,
    ) -> CodexUsageResult:
        """Fetch Codex usage and quota evidence via HTTP."""
        request = build_codex_usage_request(
            command=command,
            credentials=credentials,
            settings=self.usage_request_settings,
        )
        try:
            response = self._get(request)
        except httpx.HTTPError as err:
            return map_codex_usage_transport_error(err)

        return map_codex_usage_response(
            CodexUsageResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                json_body=_safe_json_body(response),
            )
        )

    def _post(self, request: CodexBackendRequest) -> httpx.Response:
        if self.client is not None:
            return self.client.post(
                request.url,
                headers=dict(request.headers),
                json=dict(request.json_payload),
                timeout=self.timeout,
            )
        with httpx.Client(timeout=self.timeout) as client:
            return client.post(
                request.url,
                headers=dict(request.headers),
                json=dict(request.json_payload),
            )

    def _get(self, request: CodexUsageRequest) -> httpx.Response:
        if self.client is not None:
            return self.client.get(
                request.url,
                headers=dict(request.headers),
                timeout=self.timeout,
            )
        with httpx.Client(timeout=self.timeout) as client:
            return client.get(
                request.url,
                headers=dict(request.headers),
            )


def _safe_json_body(response: httpx.Response) -> object:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return response.text
    try:
        return response.json()
    except ValueError:
        return response.text
