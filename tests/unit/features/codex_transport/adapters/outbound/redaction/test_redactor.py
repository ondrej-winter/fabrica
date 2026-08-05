"""Tests for Codex transport diagnostic redaction."""

from collections.abc import Mapping
from typing import cast

import pytest

from fabrica.features.codex_transport.adapters.outbound.redaction import (
    REDACTED_VALUE,
    redact_mapping,
    redact_metadata,
    redact_metadata_value,
    redact_value,
)
from fabrica.features.codex_transport.application.dtos.observations import SafeObservationValue

MAX_REDACTED_STRING_LENGTH = 160


def test_redact_mapping_masks_known_sensitive_keys_case_insensitively() -> None:
    diagnostic = {
        "access_token": "synthetic-access-token",
        "Refresh-Token": "synthetic-refresh-token",
        "Authorization": "Bearer synthetic-token",
        "Cookie": "session=synthetic-session",
        "api_key": "synthetic-api-key",
        "http_status": 401,
    }

    redacted = redact_mapping(diagnostic)

    assert redacted == {
        "access_token": REDACTED_VALUE,
        "Refresh-Token": REDACTED_VALUE,
        "Authorization": REDACTED_VALUE,
        "Cookie": REDACTED_VALUE,
        "api_key": REDACTED_VALUE,
        "http_status": 401,
    }


def test_redact_mapping_handles_nested_containers_without_mutating_inputs() -> None:
    diagnostic = {
        "headers": {"Authorization": "Bearer synthetic-token"},
        "events": [
            {"message": "request started", "id_token": "synthetic-id-token"},
            {"message": "request finished", "status": 200},
        ],
    }

    redacted = redact_mapping(diagnostic)

    cast("dict[str, object]", diagnostic["headers"])["Authorization"] = "mutated"

    assert redacted["headers"] == {"Authorization": REDACTED_VALUE}
    assert redacted["events"] == (
        {"message": "request started", "id_token": REDACTED_VALUE},
        {"message": "request finished", "status": 200},
    )


def test_redact_mapping_redacts_account_identifiers_instead_of_partially_exposing_them() -> None:
    redacted = redact_mapping(
        {
            "account_id": "acct-synthetic-123456789",
            "ChatGPT-Account-ID": "acct-synthetic-123456789",
            "email": "person@example.invalid",
        }
    )

    assert redacted == {
        "account_id": REDACTED_VALUE,
        "ChatGPT-Account-ID": REDACTED_VALUE,
        "email": REDACTED_VALUE,
    }


def test_redact_value_masks_authorization_like_scalar_strings() -> None:
    assert redact_value("Bearer synthetic-token") == REDACTED_VALUE
    assert redact_value("Basic synthetic-token") == REDACTED_VALUE


def test_redact_value_bounds_long_strings_without_hiding_short_safe_strings() -> None:
    assert redact_value("backend returned expected response shape") == "backend returned expected response shape"

    redacted = redact_value("x" * 200)

    assert isinstance(redacted, str)
    assert len(redacted) <= MAX_REDACTED_STRING_LENGTH
    assert redacted.endswith("…<truncated>")


def test_redact_mapping_returns_immutable_mapping() -> None:
    redacted = redact_mapping({"http_status": 200})

    with pytest.raises(TypeError):
        cast("dict[str, object]", redacted)["http_status"] = 500


def test_redact_metadata_returns_scalar_observation_values() -> None:
    redacted = redact_metadata(
        {
            "Authorization": "Bearer synthetic-token",
            "headers": {"status": 200},
            "events": [{"message": "started"}, {"message": "finished"}],
            "body": b"synthetic bytes",
            "ok": True,
        }
    )

    assert redacted == {
        "Authorization": REDACTED_VALUE,
        "headers": "<mapping length=1>",
        "events": "<sequence length=2>",
        "body": "<bytes length=15>",
        "ok": True,
    }
    assert all(_is_safe_observation_value(value) for value in redacted.values())


def test_redact_metadata_returns_immutable_mapping() -> None:
    redacted = redact_metadata({"http_status": 200})

    with pytest.raises(TypeError):
        cast("dict[str, object]", redacted)["http_status"] = 500


def test_redact_metadata_value_masks_auth_like_scalar_strings() -> None:
    assert redact_metadata_value("Bearer synthetic-token") == REDACTED_VALUE
    assert redact_metadata_value("Basic synthetic-token") == REDACTED_VALUE


def test_redact_value_returns_safe_descriptions_for_bytes_and_unknown_objects() -> None:
    class SyntheticDiagnostic:
        pass

    assert redact_value(b"synthetic bytes") == "<bytes length=15>"
    assert redact_value(SyntheticDiagnostic()) == "<SyntheticDiagnostic>"
    assert isinstance(redact_mapping({"nested": {"status": 200}})["nested"], Mapping)


def _is_safe_observation_value(value: object) -> bool:
    return isinstance(value, SafeObservationValue)
