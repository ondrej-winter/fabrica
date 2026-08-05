"""Tests for the Codex transport application package API."""

from fabrica.features.codex_transport import application
from fabrica.features.codex_transport.application.ports import (
    CodexBackend,
    CodexCredentialStore,
    CodexUsageBackend,
)
from fabrica.features.codex_transport.application.use_cases import (
    CompleteWithCodexTransport,
    ProbeCodexTransport,
    ProbeCodexUsage,
)


def test_application_package_exports_public_use_cases_and_ports() -> None:
    assert application.CompleteWithCodexTransport is CompleteWithCodexTransport
    assert application.ProbeCodexTransport is ProbeCodexTransport
    assert application.ProbeCodexUsage is ProbeCodexUsage
    assert application.CodexBackend is CodexBackend
    assert application.CodexCredentialStore is CodexCredentialStore
    assert application.CodexUsageBackend is CodexUsageBackend
