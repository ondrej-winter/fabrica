"""Opt-in live integration test for the Codex-backed local agent runtime."""

import os
from pathlib import Path

import pytest

from fabrica.bootstrap import create_codex_runtime
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand, LocalAgentRunStatus
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import CodexBackendRequestSettings

_RUN_LIVE_CODEX_TESTS_ENV = "FABRICA_RUN_LIVE_CODEX_TESTS"
_CODEX_AUTH_FILE_ENV = "FABRICA_CODEX_AUTH_FILE"
_LIVE_TEST_ENABLED_VALUE = "1"
_DEFAULT_CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"
_LIVE_CODEX_MODEL = "gpt-5.3-codex-spark"
_LIVE_CODEX_REASONING_EFFORT = "low"
_PONG_PROMPT = "Reply with the single word: pong"


@pytest.mark.live_codex
def test_live_codex_backed_runtime_returns_pong_when_explicitly_enabled() -> None:
    """Run one credential-backed live runtime call only when explicitly enabled."""
    if os.environ.get(_RUN_LIVE_CODEX_TESTS_ENV) != _LIVE_TEST_ENABLED_VALUE:
        pytest.skip(f"set {_RUN_LIVE_CODEX_TESTS_ENV}=1 to run live Codex runtime tests")

    runtime = create_codex_runtime(
        auth_file_path=_resolve_auth_file_path(),
        request_settings=CodexBackendRequestSettings(
            model=_LIVE_CODEX_MODEL,
            reasoning_effort=_LIVE_CODEX_REASONING_EFFORT,
        ),
    )

    result = runtime.run(LocalAgentRunCommand(prompt=_PONG_PROMPT))

    if result.status is not LocalAgentRunStatus.SUCCESS:
        pytest.fail(f"live Codex-backed runtime failed with redacted observations: {result.observations}")

    assert result.output_text is not None
    assert result.output_text.strip().lower() == "pong"


def _resolve_auth_file_path() -> Path:
    auth_file_override = os.environ.get(_CODEX_AUTH_FILE_ENV)
    if auth_file_override is not None and auth_file_override.strip() != "":
        return Path(auth_file_override).expanduser()
    return _DEFAULT_CODEX_AUTH_FILE
