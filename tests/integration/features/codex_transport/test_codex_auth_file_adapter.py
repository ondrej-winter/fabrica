"""Offline integration tests for the Codex auth-file adapter."""

import json
from pathlib import Path

from fabrica.features.codex_transport.adapters.outbound.codex_auth_file import CodexAuthFileCredentialStore
from fabrica.features.codex_transport.application.dtos import CodexCredentials

SYNTHETIC_ACCESS_TOKEN = "synthetic-access-token"  # noqa: S105 - synthetic test value, not a secret.
SYNTHETIC_ACCOUNT_ID = "synthetic-account-id"


def test_auth_file_adapter_reads_synthetic_temp_file_without_mutating_it(tmp_path: Path) -> None:
    auth_file_path = tmp_path / "auth.json"
    auth_payload = {
        "auth_mode": "chatgpt",
        "tokens": {
            "access_token": SYNTHETIC_ACCESS_TOKEN,
            "account_id": SYNTHETIC_ACCOUNT_ID,
        },
    }
    original_contents = json.dumps(auth_payload)
    auth_file_path.write_text(original_contents, encoding="utf-8")

    credentials = CodexAuthFileCredentialStore(auth_file_path).load()

    assert credentials == CodexCredentials(
        access_token=SYNTHETIC_ACCESS_TOKEN,
        account_id=SYNTHETIC_ACCOUNT_ID,
    )
    assert auth_file_path.read_text(encoding="utf-8") == original_contents
