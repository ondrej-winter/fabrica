"""Use case for probing Codex backend transport viability."""

from fabrica.features.codex_transport.application.dtos import (
    CodexTransportObservation,
    CodexTransportProbeCommand,
    CodexTransportResult,
    CodexTransportStatus,
)
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialStoreError,
)
from fabrica.features.codex_transport.application.ports import CodexBackend, CodexCredentialStore


class ProbeCodexTransport:
    """Orchestrate credential loading and one backend transport probe."""

    def __init__(self, credential_store: CodexCredentialStore, backend: CodexBackend) -> None:
        self._credential_store = credential_store
        self._backend = backend

    def probe(self, command: CodexTransportProbeCommand) -> CodexTransportResult:
        """Run one non-streaming Codex transport probe."""
        try:
            credentials = self._credential_store.load()
        except CodexCredentialAuthenticationError as err:
            return _credential_failure_result(
                status=CodexTransportStatus.AUTHENTICATION_FAILED,
                message="credential loading failed authentication",
                err=err,
            )
        except CodexCredentialStoreError as err:
            return _credential_failure_result(
                status=CodexTransportStatus.CREDENTIAL_ERROR,
                message="credential loading failed",
                err=err,
            )

        return self._backend.execute_probe(command=command, credentials=credentials)


def _credential_failure_result(
    *,
    status: CodexTransportStatus,
    message: str,
    err: CodexCredentialStoreError,
) -> CodexTransportResult:
    return CodexTransportResult(
        status=status,
        observations=(
            CodexTransportObservation(
                message=message,
                metadata={"error_type": type(err).__name__},
            ),
        ),
    )
