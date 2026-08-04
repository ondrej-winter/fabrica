"""Tests for Codex transport probe orchestration."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportObservation,
    CodexTransportProbeCommand,
    CodexTransportResult,
    CodexTransportStatus,
)
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialUnavailableError,
)
from fabrica.features.codex_transport.application.use_cases import ProbeCodexTransport


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
class FakeCodexBackend:
    result: CodexTransportResult
    calls: list[tuple[CodexTransportProbeCommand, CodexCredentials]] = field(default_factory=list)

    def execute_probe(
        self,
        command: CodexTransportProbeCommand,
        credentials: CodexCredentials,
    ) -> CodexTransportResult:
        self.calls.append((command, credentials))
        return self.result

    def complete(
        self,
        command: CodexCompletionCommand,
        credentials: CodexCredentials,
    ) -> CodexTransportResult:
        return self.execute_probe(CodexTransportProbeCommand(prompt=command.prompt), credentials)


def test_probe_loads_credentials_and_executes_backend_probe() -> None:
    credentials = CodexCredentials(
        access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
        account_id="synthetic-account",
    )
    command = CodexTransportProbeCommand(prompt="Reply with the single word: pong")
    backend_result = CodexTransportResult(
        status=CodexTransportStatus.SUCCESS,
        output_text="pong",
        observations=(CodexTransportObservation(message="backend probe succeeded"),),
    )
    credential_store = FakeCredentialStore(credentials=credentials)
    backend = FakeCodexBackend(result=backend_result)

    result = ProbeCodexTransport(credential_store=credential_store, backend=backend).probe(command)

    assert result == backend_result
    assert credential_store.load_count == 1
    assert backend.calls == [(command, credentials)]


def test_probe_returns_credential_error_when_credentials_cannot_be_loaded() -> None:
    command = CodexTransportProbeCommand(prompt="Reply with the single word: pong")
    credential_store = FakeCredentialStore(error=CodexCredentialUnavailableError("synthetic missing auth file"))
    backend = FakeCodexBackend(result=CodexTransportResult(status=CodexTransportStatus.SUCCESS))

    result = ProbeCodexTransport(credential_store=credential_store, backend=backend).probe(command)

    assert result.status is CodexTransportStatus.CREDENTIAL_ERROR
    assert result.succeeded is False
    assert result.output_text is None
    assert result.observations == (
        CodexTransportObservation(
            message="credential loading failed",
            metadata={"error_type": "CodexCredentialUnavailableError"},
        ),
    )
    assert backend.calls == []


def test_probe_returns_authentication_failed_for_credential_authentication_failures() -> None:
    command = CodexTransportProbeCommand(prompt="Reply with the single word: pong")
    credential_store = FakeCredentialStore(error=CodexCredentialAuthenticationError("synthetic unsupported auth mode"))
    backend = FakeCodexBackend(result=CodexTransportResult(status=CodexTransportStatus.SUCCESS))

    result = ProbeCodexTransport(credential_store=credential_store, backend=backend).probe(command)

    assert result.status is CodexTransportStatus.AUTHENTICATION_FAILED
    assert result.observations == (
        CodexTransportObservation(
            message="credential loading failed authentication",
            metadata={"error_type": "CodexCredentialAuthenticationError"},
        ),
    )
    assert backend.calls == []


def test_probe_passes_through_backend_failure_result() -> None:
    credentials = CodexCredentials(
        access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
        account_id="synthetic-account",
    )
    command = CodexTransportProbeCommand(prompt="Reply with the single word: pong")
    backend_result = CodexTransportResult(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        observations=(CodexTransportObservation(message="backend request failed", metadata={"category": "timeout"}),),
    )

    result = ProbeCodexTransport(
        credential_store=FakeCredentialStore(credentials=credentials),
        backend=FakeCodexBackend(result=backend_result),
    ).probe(command)

    assert result == backend_result
