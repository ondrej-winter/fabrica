"""Codex auth-file payload loading helpers."""

import json
from pathlib import Path
from typing import Any

from fabrica.features.codex_transport.application.exceptions import CodexCredentialUnavailableError

_AUTH_FILE_NOT_FOUND_MESSAGE = "Codex auth file was not found"
_AUTH_FILE_NOT_READABLE_MESSAGE = "Codex auth file could not be read"
_INVALID_JSON_MESSAGE = "Codex auth file is not valid JSON"
_NON_OBJECT_JSON_MESSAGE = "Codex auth file must contain a JSON object"


def load_auth_payload(auth_file_path: Path) -> dict[str, Any]:
    """Read and parse a Codex auth file as a JSON object."""
    try:
        contents = auth_file_path.read_text(encoding="utf-8")
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
