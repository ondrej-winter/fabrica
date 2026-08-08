"""Codex auth-file payload validation helpers."""

from typing import Any

from fabrica.features.codex_transport.application.dtos import CodexCredentials
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialUnavailableError,
)

_SUPPORTED_AUTH_MODE = "chatgpt"
_MISSING_TOKENS_MESSAGE = "Codex auth file is missing tokens"
_UNSUPPORTED_AUTH_MODE_MESSAGE = "unsupported Codex auth mode"


def validate_auth_mode(payload: dict[str, Any]) -> None:
    """Validate that the auth file uses the supported ChatGPT auth mode."""
    auth_mode = _read_required_string(payload, "auth_mode")
    if auth_mode != _SUPPORTED_AUTH_MODE:
        raise CodexCredentialAuthenticationError(_UNSUPPORTED_AUTH_MODE_MESSAGE)


def read_credentials(payload: dict[str, Any]) -> CodexCredentials:
    """Read credential fields from a validated Codex auth-file payload."""
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise CodexCredentialUnavailableError(_MISSING_TOKENS_MESSAGE)

    return CodexCredentials(
        access_token=_read_required_string(tokens, "access_token"),
        account_id=_read_required_string(tokens, "account_id"),
    )


def _read_required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or value == "":
        message = f"Codex auth file is missing required field: {key}"
        raise CodexCredentialUnavailableError(message)
    return value
