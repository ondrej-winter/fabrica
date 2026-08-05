"""Read-only credential adapter for Codex CLI auth files."""

import json
from pathlib import Path
from typing import Any

from fabrica.features.codex_transport.application.dtos import CodexCredentials
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialUnavailableError,
)

_SUPPORTED_AUTH_MODE = "chatgpt"
_AUTH_FILE_NOT_FOUND_MESSAGE = "Codex auth file was not found"
_AUTH_FILE_NOT_READABLE_MESSAGE = "Codex auth file could not be read"
_INVALID_JSON_MESSAGE = "Codex auth file is not valid JSON"
_MISSING_TOKENS_MESSAGE = "Codex auth file is missing tokens"
_NON_OBJECT_JSON_MESSAGE = "Codex auth file must contain a JSON object"
_UNSUPPORTED_AUTH_MODE_MESSAGE = "unsupported Codex auth mode"


class CodexAuthFileCredentialStore:
    """Load Codex credentials from a configured auth JSON file.

    The adapter is read-only and intentionally keeps the Codex auth-file shape
    outside the application layer. Exception messages are category-only and do
    not include raw auth payload values.
    """

    def __init__(self, auth_file_path: Path | str) -> None:
        self._auth_file_path = Path(auth_file_path).expanduser()

    def load(self) -> CodexCredentials:
        """Load ChatGPT-backed Codex credentials from the configured auth file.

        The file is read lazily on each call and must contain a JSON object with
        ``auth_mode`` set to ``"chatgpt"`` and a ``tokens`` object containing
        non-empty ``access_token`` and ``account_id`` string fields.

        Returns:
            Application credentials DTO containing secret-bearing token values.

        Raises:
            CodexCredentialAuthenticationError: The auth file uses an unsupported
                authentication mode.
            CodexCredentialUnavailableError: The file is missing, unreadable, not
                valid JSON, or missing required credential fields.

        """
        payload = self._load_payload()
        auth_mode = _read_required_string(payload, "auth_mode")
        if auth_mode != _SUPPORTED_AUTH_MODE:
            raise CodexCredentialAuthenticationError(_UNSUPPORTED_AUTH_MODE_MESSAGE)

        tokens = payload.get("tokens")
        if not isinstance(tokens, dict):
            raise CodexCredentialUnavailableError(_MISSING_TOKENS_MESSAGE)

        return CodexCredentials(
            access_token=_read_required_string(tokens, "access_token"),
            account_id=_read_required_string(tokens, "account_id"),
        )

    def _load_payload(self) -> dict[str, Any]:
        try:
            contents = self._auth_file_path.read_text(encoding="utf-8")
        except FileNotFoundError as err:
            raise CodexCredentialUnavailableError(_AUTH_FILE_NOT_FOUND_MESSAGE) from err
        except OSError as err:
            raise CodexCredentialUnavailableError(_AUTH_FILE_NOT_READABLE_MESSAGE) from err

        try:
            payload = json.loads(contents)
        except json.JSONDecodeError as err:
            raise CodexCredentialUnavailableError(_INVALID_JSON_MESSAGE) from err

        if not isinstance(payload, dict):
            raise CodexCredentialUnavailableError(_NON_OBJECT_JSON_MESSAGE)
        return payload


def _read_required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or value == "":
        message = f"Codex auth file is missing required field: {key}"
        raise CodexCredentialUnavailableError(message)
    return value
