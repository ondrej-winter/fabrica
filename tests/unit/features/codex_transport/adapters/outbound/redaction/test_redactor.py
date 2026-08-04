"""Tests for Codex transport diagnostic redaction."""

from collections.abc import Mapping
from typing import cast

import pytest

from fabrica.features.codex_transport.adapters.outbound.redaction import (
    REDACTED_VALUE,
    redact_mapping,
    redact_value,
)

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


def test_redact_value_returns_safe_descriptions_for_bytes_and_unknown_objects() -> None:
    class SyntheticDiagnostic:
        pass

    assert redact_value(b"synthetic bytes") == "<bytes length=15>"
    assert redact_value(SyntheticDiagnostic()) == "<SyntheticDiagnostic>"
    assert isinstance(redact_mapping({"nested": {"status": 200}})["nested"], Mapping)
