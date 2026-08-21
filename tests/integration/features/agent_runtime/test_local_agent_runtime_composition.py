"""Offline integration tests for local Codex-backed runtime composition."""

import asyncio
import json
from pathlib import Path

import httpx

from fabrica.adapters.outbound.httpx_client import SyncHttpxRetryClient
from fabrica.bootstrap import create_codex_runtime
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand, LocalAgentRunStatus


def test_codex_runtime_composition_runs_with_mock_transport(tmp_path: Path) -> None:
    auth_file_path = tmp_path / "auth.json"
    auth_file_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "synthetic-access-token",
                    "account_id": "synthetic-account",
                },
            },
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://chatgpt.com/backend-api/codex/responses"
        assert request.headers["Authorization"] == "Bearer synthetic-access-token"
        assert request.headers["ChatGPT-Account-ID"] == "synthetic-account"
        return httpx.Response(200, json={"output_text": "pong"})

    runtime = create_codex_runtime(
        auth_file_path=auth_file_path,
        http_client=SyncHttpxRetryClient(client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler))),
    )

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Reply with the single word: pong")))

    assert result.status is LocalAgentRunStatus.SUCCESS
    assert result.succeeded is True
    assert result.output_text == "pong"
    assert "synthetic-access-token" not in str(result.observations)
    assert "synthetic-account" not in str(result.observations)


def test_codex_runtime_factory_does_not_read_credentials_during_construction(tmp_path: Path) -> None:
    missing_auth_file_path = tmp_path / "missing-auth.json"

    runtime = create_codex_runtime(auth_file_path=missing_auth_file_path)

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Reply with the single word: pong")))

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
