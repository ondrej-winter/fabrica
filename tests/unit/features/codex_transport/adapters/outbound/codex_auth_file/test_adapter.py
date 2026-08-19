"""Tests for the read-only Codex auth-file credential adapter."""

import json
from pathlib import Path

import pytest

from fabrica.features.codex_transport.adapters.outbound.codex_auth_file import CodexAuthFileCredentialStore
from fabrica.features.codex_transport.application.dtos import CodexCredentials
from fabrica.features.codex_transport.application.exceptions import (
    CodexCredentialAuthenticationError,
    CodexCredentialUnavailableError,
)
from tests.synthetic_values import CODEX_ACCOUNT_ID_WITH_SUFFIX, CODEX_BEARER_VALUE

SYNTHETIC_ACCESS_TOKEN = CODEX_BEARER_VALUE
SYNTHETIC_ACCOUNT_ID = CODEX_ACCOUNT_ID_WITH_SUFFIX


def test_load_returns_credentials_from_chatgpt_auth_file(tmp_path: Path) -> None:
    auth_file_path = _write_auth_file(tmp_path)

    credentials = CodexAuthFileCredentialStore(auth_file_path).load()

    assert credentials == CodexCredentials(
        access_token=SYNTHETIC_ACCESS_TOKEN,
        account_id=SYNTHETIC_ACCOUNT_ID,
    )


def test_constructor_accepts_string_path_for_config_boundaries(tmp_path: Path) -> None:
    auth_file_path = _write_auth_file(tmp_path)

    credentials = CodexAuthFileCredentialStore(str(auth_file_path)).load()

    assert credentials == CodexCredentials(
        access_token=SYNTHETIC_ACCESS_TOKEN,
        account_id=SYNTHETIC_ACCOUNT_ID,
    )


def test_constructor_expands_user_home_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_path = tmp_path / "home"
    _write_auth_file(home_path / ".codex")
    monkeypatch.setenv("HOME", str(home_path))

    credentials = CodexAuthFileCredentialStore(Path("~/.codex/auth.json")).load()

    assert credentials == CodexCredentials(
        access_token=SYNTHETIC_ACCESS_TOKEN,
        account_id=SYNTHETIC_ACCOUNT_ID,
    )


def test_load_raises_credential_unavailable_when_file_is_missing(tmp_path: Path) -> None:
    auth_file_path = tmp_path / "missing-auth.json"

    with pytest.raises(CodexCredentialUnavailableError, match="not found"):
        CodexAuthFileCredentialStore(auth_file_path).load()


def test_load_raises_credential_unavailable_for_invalid_json(tmp_path: Path) -> None:
    auth_file_path = tmp_path / "auth.json"
    auth_file_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(CodexCredentialUnavailableError, match="valid JSON"):
        CodexAuthFileCredentialStore(auth_file_path).load()


def test_load_raises_credential_unavailable_for_non_object_json(tmp_path: Path) -> None:
    auth_file_path = tmp_path / "auth.json"
    auth_file_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(CodexCredentialUnavailableError, match="JSON object"):
        CodexAuthFileCredentialStore(auth_file_path).load()


def test_load_raises_authentication_error_for_unsupported_auth_mode(tmp_path: Path) -> None:
    auth_file_path = _write_auth_file(tmp_path, auth_mode="api_key")

    with pytest.raises(CodexCredentialAuthenticationError, match="unsupported Codex auth mode"):
        CodexAuthFileCredentialStore(auth_file_path).load()


@pytest.mark.parametrize(
    ("payload_override", "expected_message"),
    [
        ({"tokens": {}}, "access_token"),
        ({"tokens": {"access_token": ""}}, "access_token"),
        ({"tokens": {"access_token": SYNTHETIC_ACCESS_TOKEN}}, "account_id"),
        ({"tokens": {"access_token": SYNTHETIC_ACCESS_TOKEN, "account_id": ""}}, "account_id"),
        ({"tokens": None}, "tokens"),
    ],
)
def test_load_raises_credential_unavailable_for_missing_required_fields(
    tmp_path: Path,
    payload_override: dict[str, object],
    expected_message: str,
) -> None:
    auth_file_path = _write_auth_file(tmp_path, payload_override=payload_override)

    with pytest.raises(CodexCredentialUnavailableError, match=expected_message):
        CodexAuthFileCredentialStore(auth_file_path).load()


def test_load_failure_messages_do_not_expose_synthetic_secret_values(tmp_path: Path) -> None:
    auth_file_path = _write_auth_file(tmp_path, auth_mode="api_key")

    with pytest.raises(CodexCredentialAuthenticationError) as exc_info:
        CodexAuthFileCredentialStore(auth_file_path).load()

    message = str(exc_info.value)
    assert SYNTHETIC_ACCESS_TOKEN not in message
    assert SYNTHETIC_ACCOUNT_ID not in message


def _write_auth_file(
    tmp_path: Path,
    *,
    auth_mode: str = "chatgpt",
    payload_override: dict[str, object] | None = None,
) -> Path:
    payload: dict[str, object] = {
        "auth_mode": auth_mode,
        "tokens": {
            "access_token": SYNTHETIC_ACCESS_TOKEN,
            "account_id": SYNTHETIC_ACCOUNT_ID,
        },
    }
    if payload_override is not None:
        payload.update(payload_override)

    auth_file_path = tmp_path / "auth.json"
    auth_file_path.parent.mkdir(parents=True, exist_ok=True)
    auth_file_path.write_text(json.dumps(payload), encoding="utf-8")
    return auth_file_path
