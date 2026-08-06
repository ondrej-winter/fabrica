"""Opt-in live integration test for the Codex backend transport path."""

import os
from pathlib import Path

import pytest

from fabrica.features.codex_transport.adapters.outbound.codex_auth_file import CodexAuthFileCredentialStore
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import (
    CodexBackendHttpAdapter,
    CodexBackendRequestSettings,
)
from fabrica.features.codex_transport.application.dtos import CodexCompletionCommand, CodexTransportStatus
from fabrica.features.codex_transport.application.use_cases import CompleteWithCodexTransport

_RUN_LIVE_CODEX_TESTS_ENV = "FABRICA_RUN_LIVE_CODEX_TESTS"
_CODEX_AUTH_FILE_ENV = "FABRICA_CODEX_AUTH_FILE"
_LIVE_TEST_ENABLED_VALUE = "1"
_DEFAULT_CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"
_LIVE_CODEX_MODEL = "gpt-5.3-codex-spark"
_LIVE_CODEX_REASONING_EFFORT = "low"
_PONG_PROMPT = "Reply with the single word: pong"


@pytest.mark.live_codex
def test_live_codex_backend_completion_returns_pong_when_explicitly_enabled() -> None:
    """Run one credential-backed live completion only when explicitly enabled."""
    if os.environ.get(_RUN_LIVE_CODEX_TESTS_ENV) != _LIVE_TEST_ENABLED_VALUE:
        pytest.skip(f"set {_RUN_LIVE_CODEX_TESTS_ENV}=1 to run live Codex backend tests")

    use_case = CompleteWithCodexTransport(
        credential_store=CodexAuthFileCredentialStore(_resolve_auth_file_path()),
        backend=CodexBackendHttpAdapter(
            request_settings=CodexBackendRequestSettings(
                model=_LIVE_CODEX_MODEL,
                reasoning_effort=_LIVE_CODEX_REASONING_EFFORT,
            )
        ),
    )

    result = use_case.complete(CodexCompletionCommand(prompt=_PONG_PROMPT))

    assert isinstance(result.status, CodexTransportStatus)
    if result.status is not CodexTransportStatus.SUCCESS:
        pytest.fail(f"live Codex completion failed with redacted observations: {result.observations}")

    assert result.output_text is not None
    assert result.output_text.strip().lower() == "pong"


def _resolve_auth_file_path() -> Path:
    auth_file_override = os.environ.get(_CODEX_AUTH_FILE_ENV)
    if auth_file_override is not None and auth_file_override.strip() != "":
        return Path(auth_file_override).expanduser()
    return _DEFAULT_CODEX_AUTH_FILE
