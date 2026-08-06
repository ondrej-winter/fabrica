"""Backend execution port for Codex transport completions."""

from typing import Protocol

from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportResult,
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
