"""Application-owned transport ports for Codex operations."""

from typing import Protocol

from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportResult,
    CodexUsageProbeCommand,
    CodexUsageResult,
)


class CodexBackend(Protocol):
    """Outbound port for Codex backend completions."""

    def complete(
        self,
        command: CodexCompletionCommand,
        credentials: CodexCredentials,
    ) -> CodexTransportResult:
        """Execute one Codex completion and return a normalized result."""
        ...


class CodexUsageBackend(Protocol):
    """Outbound port for retrieving Codex usage and quota evidence."""

    def fetch_usage(
        self,
        command: CodexUsageProbeCommand,
        credentials: CodexCredentials,
    ) -> CodexUsageResult:
        """Fetch usage evidence with application-owned command and credentials."""
        ...


class CodexCredentialStore(Protocol):
    """Outbound port for loading Codex credentials into application DTOs."""

    def load(self) -> CodexCredentials:
        """Load credentials required for one Codex transport operation.

        Raises:
            CodexCredentialStoreError: Credentials could not be safely loaded or
                are not usable for Codex authentication.

        """
        ...
