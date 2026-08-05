"""Use case for probing Codex backend transport viability."""

from fabrica.features.codex_transport.application.dtos import (
    CodexTransportProbeCommand,
    CodexTransportResult,
    CodexTransportStatus,
)
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialStoreError,
)
from fabrica.features.codex_transport.application.ports import CodexBackend, CodexCredentialStore
from fabrica.features.codex_transport.application.use_cases._credential_failures import (
    credential_transport_failure_result,
)


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
            return credential_transport_failure_result(
                status=CodexTransportStatus.AUTHENTICATION_FAILED,
                message="credential loading failed authentication",
                err=err,
            )
        except CodexCredentialStoreError as err:
            return credential_transport_failure_result(
                status=CodexTransportStatus.CREDENTIAL_ERROR,
                message="credential loading failed",
                err=err,
            )

        return self._backend.execute_probe(command=command, credentials=credentials)
