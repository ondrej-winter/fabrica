"""Tests for Codex transport application DTO contracts."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportObservation,
    CodexTransportProbeCommand,
    CodexTransportResult,
    CodexTransportStatus,
    SafeObservationValue,
)


def test_transport_status_values_match_normalized_contract() -> None:
    assert {status.value for status in CodexTransportStatus} == {
        "success",
        "authentication_failed",
        "rate_limited",
        "quota_exceeded",
        "backend_shape_mismatch",
        "transport_error",
        "credential_error",
    }


def test_probe_command_carries_prompt_without_backend_shape() -> None:
    command = CodexTransportProbeCommand(prompt="Reply with the single word: pong")

    assert command.prompt == "Reply with the single word: pong"


@pytest.mark.parametrize("command_type", [CodexCompletionCommand, CodexTransportProbeCommand])
def test_prompt_commands_reject_empty_prompts(
    command_type: type[CodexCompletionCommand | CodexTransportProbeCommand],
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        command_type(prompt="  ")


def test_result_exposes_success_helper_and_safe_observations() -> None:
    observation = CodexTransportObservation(
        message="backend returned expected response shape",
        metadata={"http_status": 200, "response_shape": "responses"},
    )
    result = CodexTransportResult(
        status=CodexTransportStatus.SUCCESS,
        output_text="pong",
        observations=(observation,),
    )

    assert result.succeeded is True
    assert result.output_text == "pong"
    assert result.observations == (observation,)


def test_non_success_result_is_not_successful() -> None:
    result = CodexTransportResult(status=CodexTransportStatus.AUTHENTICATION_FAILED)

    assert result.succeeded is False
    assert result.output_text is None
    assert result.observations == ()


def test_success_result_requires_output_text() -> None:
    with pytest.raises(ValueError, match="must include output_text"):
        CodexTransportResult(status=CodexTransportStatus.SUCCESS)


def test_non_success_result_rejects_output_text() -> None:
    with pytest.raises(ValueError, match="must not include output_text"):
        CodexTransportResult(status=CodexTransportStatus.TRANSPORT_ERROR, output_text="ignored")


def test_observation_metadata_is_copied_and_immutable() -> None:
    metadata = {"http_status": 429, "category": "rate_limit"}
    observation = CodexTransportObservation(message="request was rate limited", metadata=metadata)

    metadata["category"] = "mutated"

    assert observation.metadata["category"] == "rate_limit"
    with pytest.raises(TypeError):
        cast("dict[str, object]", observation.metadata)["category"] = "changed"


def test_observation_rejects_non_scalar_metadata_values() -> None:
    unsafe_metadata = cast("dict[str, SafeObservationValue]", {"nested": {"raw": "payload"}})

    with pytest.raises(TypeError, match="bounded scalar"):
        CodexTransportObservation(message="unsafe", metadata=unsafe_metadata)


def test_credentials_are_immutable_secret_bearing_boundary_values() -> None:
    access_token = "synthetic-token"  # noqa: S105 - synthetic test value, not a secret.
    credentials = CodexCredentials(access_token=access_token, account_id="synthetic-account")

    assert credentials.access_token == access_token
    assert credentials.account_id == "synthetic-account"
    with pytest.raises(FrozenInstanceError):
        setattr(credentials, "access_token", "replacement")  # noqa: B010
