"""Use case for running one Codex backend completion."""

from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
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


class CompleteWithCodexTransport:
    """Orchestrate credential loading and one backend completion."""

    def __init__(self, credential_store: CodexCredentialStore, backend: CodexBackend) -> None:
        self._credential_store = credential_store
        self._backend = backend

    def complete(self, command: CodexCompletionCommand) -> CodexTransportResult:
        """Run one non-streaming Codex completion."""
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

        return self._backend.complete(command=command, credentials=credentials)
