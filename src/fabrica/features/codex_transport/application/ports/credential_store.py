"""Credential-loading port for Codex transport probing."""

from typing import Protocol

from fabrica.features.codex_transport.application.dtos import CodexCredentials


class CodexCredentialStore(Protocol):
    """Outbound port for loading Codex credentials into application DTOs."""

    def load(self) -> CodexCredentials:
        """Load credentials required for one Codex transport operation.

        Raises:
            CodexCredentialStoreError: Credentials could not be safely loaded or
                are not usable for Codex authentication.

        """
        ...
