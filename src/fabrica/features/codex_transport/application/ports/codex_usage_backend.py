"""Backend usage evidence port for Codex transport probing."""

from typing import Protocol

from fabrica.features.codex_transport.application.dtos import (
    CodexCredentials,
    CodexUsageProbeCommand,
    CodexUsageResult,
)


class CodexUsageBackend(Protocol):
    """Outbound port for retrieving Codex usage and quota evidence."""

    def fetch_usage(
        self,
        command: CodexUsageProbeCommand,
        credentials: CodexCredentials,
    ) -> CodexUsageResult:
        """Fetch usage evidence with application-owned command and credentials."""
        ...
