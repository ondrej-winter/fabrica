"""Read-only credential adapter for Codex CLI auth files."""

from pathlib import Path

from fabrica.features.codex_transport.adapters.outbound.codex_auth_file.payload import load_auth_payload
from fabrica.features.codex_transport.adapters.outbound.codex_auth_file.validation import (
    read_credentials,
    validate_auth_mode,
)
from fabrica.features.codex_transport.application.dtos import CodexCredentials

__all__ = ["CodexAuthFileCredentialStore"]


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
        payload = load_auth_payload(self._auth_file_path)
        validate_auth_mode(payload)
        return read_credentials(payload)
