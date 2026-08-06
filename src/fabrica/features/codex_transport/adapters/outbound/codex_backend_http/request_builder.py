"""Build ChatGPT Codex backend requests from application boundary values.

The request builders are adapter-owned contracts: they translate application
DTOs and credentials into the current Codex HTTP wire shape without exposing
that shape to the application layer.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fabrica.features.codex_transport.adapters.outbound.redaction import redact_metadata
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportObservation,
    CodexUsageProbeCommand,
)

DEFAULT_CODEX_BACKEND_BASE_URL = "https://chatgpt.com/backend-api/"
DEFAULT_CODEX_BACKEND_PATH = "codex/responses"
DEFAULT_CODEX_USAGE_PATH = "api/codex/usage"
DEFAULT_CODEX_MODEL = "gpt-5.6-sol"
DEFAULT_CODEX_PRODUCT_SKU = "codex"


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


def _join_url(*, base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
