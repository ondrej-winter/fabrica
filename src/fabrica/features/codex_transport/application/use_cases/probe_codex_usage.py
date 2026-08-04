"""Use case for probing Codex usage and quota evidence."""

from fabrica.features.codex_transport.application.dtos import (
    CodexTransportObservation,
    CodexUsageProbeCommand,
    CodexUsageResult,
    CodexUsageStatus,
)
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialStoreError,
)
from fabrica.features.codex_transport.application.ports import CodexCredentialStore, CodexUsageBackend


class ProbeCodexUsage:
    """Orchestrate credential loading and one usage evidence probe."""

    def __init__(self, credential_store: CodexCredentialStore, backend: CodexUsageBackend) -> None:
        self._credential_store = credential_store
        self._backend = backend

    def probe(self, command: CodexUsageProbeCommand) -> CodexUsageResult:
        """Run one Codex usage evidence probe."""
        try:
            credentials = self._credential_store.load()
        except CodexCredentialAuthenticationError as err:
            return _credential_failure_result(
                status=CodexUsageStatus.AUTHENTICATION_FAILED,
                message="credential loading failed authentication",
                err=err,
            )
        except CodexCredentialStoreError as err:
            return _credential_failure_result(
                status=CodexUsageStatus.CREDENTIAL_ERROR,
                message="credential loading failed",
                err=err,
            )

        return self._backend.fetch_usage(command=command, credentials=credentials)


def _credential_failure_result(
    *,
    status: CodexUsageStatus,
    message: str,
    err: CodexCredentialStoreError,
) -> CodexUsageResult:
    return CodexUsageResult(
        status=status,
        observations=(
            CodexTransportObservation(
                message=message,
                metadata={"error_type": type(err).__name__},
            ),
        ),
    )
