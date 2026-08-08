"""Use cases for Codex transport completion and usage probing."""

from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
    CodexUsageProbeCommand,
    CodexUsageResult,
)
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialStoreError,
)
from fabrica.features.codex_transport.application.ports import (
    CodexBackend,
    CodexCredentialStore,
    CodexUsageBackend,
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
            return _credential_transport_failure_result(
                status=CodexTransportStatus.AUTHENTICATION_FAILED,
                message="credential loading failed authentication",
                err=err,
            )
        except CodexCredentialStoreError as err:
            return _credential_transport_failure_result(
                status=CodexTransportStatus.CREDENTIAL_ERROR,
                message="credential loading failed",
                err=err,
            )

        return self._backend.complete(command=command, credentials=credentials)


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
            return _credential_usage_failure_result(
                status=CodexTransportStatus.AUTHENTICATION_FAILED,
                message="credential loading failed authentication",
                err=err,
            )
        except CodexCredentialStoreError as err:
            return _credential_usage_failure_result(
                status=CodexTransportStatus.CREDENTIAL_ERROR,
                message="credential loading failed",
                err=err,
            )

        return self._backend.fetch_usage(command=command, credentials=credentials)


def _credential_transport_failure_result(
    *,
    status: CodexTransportStatus,
    message: str,
    err: CodexCredentialStoreError,
) -> CodexTransportResult:
    return CodexTransportResult(
        status=status,
        observations=(_credential_failure_observation(message=message, err=err),),
    )


def _credential_usage_failure_result(
    *,
    status: CodexTransportStatus,
    message: str,
    err: CodexCredentialStoreError,
) -> CodexUsageResult:
    return CodexUsageResult(
        status=status,
        observations=(_credential_failure_observation(message=message, err=err),),
    )


def _credential_failure_observation(
    *,
    message: str,
    err: CodexCredentialStoreError,
) -> CodexTransportObservation:
    return CodexTransportObservation(
        message=message,
        metadata={"error_type": type(err).__name__},
    )
