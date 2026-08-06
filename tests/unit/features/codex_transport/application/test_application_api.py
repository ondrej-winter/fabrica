"""Tests for the Codex transport application package API."""

from pathlib import Path

from fabrica.features.codex_transport import application
from fabrica.features.codex_transport.application.ports import (
    CodexBackend,
    CodexCredentialStore,
    CodexUsageBackend,
)
from fabrica.features.codex_transport.application.use_cases import (
    CompleteWithCodexTransport,
    ProbeCodexUsage,
)


def test_application_package_exports_public_use_cases_and_ports() -> None:
    assert application.CompleteWithCodexTransport is CompleteWithCodexTransport
    assert application.CompleteWithCodexTransport is CompleteWithCodexTransport
    assert application.ProbeCodexUsage is ProbeCodexUsage
    assert application.CodexBackend is CodexBackend
    assert application.CodexCredentialStore is CodexCredentialStore
    assert application.CodexUsageBackend is CodexUsageBackend


def test_codex_transport_application_does_not_import_agent_runtime_slice() -> None:
    application_root = Path("src/fabrica/features/codex_transport/application")

    offending_files = tuple(
        path for path in application_root.rglob("*.py") if "fabrica.features.agent_runtime" in path.read_text()
    )

    assert offending_files == ()
