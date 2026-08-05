"""Credential failure result mapping for Codex transport use cases."""

from fabrica.features.codex_transport.application.dtos import (
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
    CodexUsageResult,
    CodexUsageStatus,
)
from fabrica.features.codex_transport.application.exceptions import CodexCredentialStoreError


def credential_transport_failure_result(
    *,
    status: CodexTransportStatus,
    message: str,
    err: CodexCredentialStoreError,
) -> CodexTransportResult:
    """Return the normalized transport result for a credential-loading failure."""
    return CodexTransportResult(
        status=status,
        observations=(_credential_failure_observation(message=message, err=err),),
    )


def credential_usage_failure_result(
    *,
    status: CodexUsageStatus,
    message: str,
    err: CodexCredentialStoreError,
) -> CodexUsageResult:
    """Return the normalized usage result for a credential-loading failure."""
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
