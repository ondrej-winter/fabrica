"""Tests for Codex usage evidence probe orchestration."""

from dataclasses import dataclass, field
from typing import cast

import pytest

from fabrica.features.codex_transport.application.dtos import (
    CodexCredentials,
    CodexTransportObservation,
    CodexTransportStatus,
    CodexUsageEvidence,
    CodexUsageProbeCommand,
    CodexUsageResult,
    SafeUsageEvidenceValue,
)
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialUnavailableError,
)
from fabrica.features.codex_transport.application.use_cases import ProbeCodexUsage


@dataclass
class FakeCredentialStore:
    credentials: CodexCredentials | None = None
    error: Exception | None = None
    load_count: int = 0

    def load(self) -> CodexCredentials:
        self.load_count += 1
        if self.error is not None:
            raise self.error
        if self.credentials is None:
            pytest.fail("test fake requires credentials or error")
        return self.credentials


@dataclass
class FakeUsageBackend:
    result: CodexUsageResult
    calls: list[tuple[CodexUsageProbeCommand, CodexCredentials]] = field(default_factory=list)

    def fetch_usage(
        self,
        command: CodexUsageProbeCommand,
        credentials: CodexCredentials,
    ) -> CodexUsageResult:
        self.calls.append((command, credentials))
        return self.result


def test_probe_loads_credentials_and_fetches_usage_evidence() -> None:
    credentials = CodexCredentials(
        access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
        account_id="synthetic-account",
    )
    command = CodexUsageProbeCommand()
    backend_result = CodexUsageResult(
        status=CodexTransportStatus.SUCCESS,
        evidence=CodexUsageEvidence({"plan_type": "synthetic-pro"}),
        observations=(CodexTransportObservation(message="usage evidence retrieved"),),
    )
    credential_store = FakeCredentialStore(credentials=credentials)
    backend = FakeUsageBackend(result=backend_result)

    result = ProbeCodexUsage(credential_store=credential_store, backend=backend).probe(command)

    assert result == backend_result
    assert credential_store.load_count == 1
    assert backend.calls == [(command, credentials)]


def test_probe_returns_credential_error_when_credentials_cannot_be_loaded() -> None:
    credential_store = FakeCredentialStore(error=CodexCredentialUnavailableError("synthetic missing auth file"))
    backend = FakeUsageBackend(result=CodexUsageResult(status=CodexTransportStatus.TRANSPORT_ERROR))

    result = ProbeCodexUsage(credential_store=credential_store, backend=backend).probe(CodexUsageProbeCommand())

    assert result.status is CodexTransportStatus.CREDENTIAL_ERROR
    assert result.succeeded is False
    assert result.evidence is None
    assert result.observations == (
        CodexTransportObservation(
            message="credential loading failed",
            metadata={"error_type": "CodexCredentialUnavailableError"},
        ),
    )
    assert backend.calls == []


def test_probe_returns_authentication_failed_for_credential_authentication_failures() -> None:
    credential_store = FakeCredentialStore(error=CodexCredentialAuthenticationError("synthetic unsupported auth mode"))
    backend = FakeUsageBackend(result=CodexUsageResult(status=CodexTransportStatus.TRANSPORT_ERROR))

    result = ProbeCodexUsage(credential_store=credential_store, backend=backend).probe(CodexUsageProbeCommand())

    assert result.status is CodexTransportStatus.AUTHENTICATION_FAILED
    assert result.observations == (
        CodexTransportObservation(
            message="credential loading failed authentication",
            metadata={"error_type": "CodexCredentialAuthenticationError"},
        ),
    )
    assert backend.calls == []


def test_usage_evidence_is_copied_and_immutable() -> None:
    original_remaining = 12
    values = {"remaining": original_remaining}
    evidence = CodexUsageEvidence(values)

    values["remaining"] = 0

    assert evidence.values["remaining"] == original_remaining
    with pytest.raises(TypeError):
        cast("dict[str, object]", evidence.values)["remaining"] = 99


def test_usage_evidence_rejects_non_scalar_values() -> None:
    unsafe_values = cast("dict[str, SafeUsageEvidenceValue]", {"nested": {"raw": "payload"}})

    with pytest.raises(TypeError, match="bounded scalar"):
        CodexUsageEvidence(unsafe_values)


def test_success_usage_result_requires_evidence() -> None:
    with pytest.raises(ValueError, match="must include evidence"):
        CodexUsageResult(status=CodexTransportStatus.SUCCESS)


def test_non_success_usage_result_rejects_evidence() -> None:
    with pytest.raises(ValueError, match="must not include evidence"):
        CodexUsageResult(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            evidence=CodexUsageEvidence({"plan_type": "synthetic-pro"}),
        )
