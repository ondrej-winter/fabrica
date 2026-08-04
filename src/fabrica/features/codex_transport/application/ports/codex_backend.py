"""Backend execution port for Codex transport probing."""

from typing import Protocol

from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportProbeCommand,
    CodexTransportResult,
)


class CodexBackend(Protocol):
    """Outbound port for Codex backend completions and compatibility probes."""

    def complete(
        self,
        command: CodexCompletionCommand,
        credentials: CodexCredentials,
    ) -> CodexTransportResult:
        """Execute one non-streaming Codex completion."""
        ...

    def execute_probe(
        self,
        command: CodexTransportProbeCommand,
        credentials: CodexCredentials,
    ) -> CodexTransportResult:
        """Execute a probe with application-owned command and credentials."""
        ...
