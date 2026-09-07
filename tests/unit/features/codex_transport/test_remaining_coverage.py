"""Focused coverage for remaining Codex transport boundary guards."""

from pathlib import Path
from typing import Any, cast

import pytest

from fabrica.features.codex_transport.adapters.outbound.codex_auth_file import payload
from fabrica.features.codex_transport.application.dtos import (
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
    CodexUsageEvidence,
    CodexUsageResult,
)
from fabrica.features.codex_transport.application.exceptions import CodexCredentialUnavailableError


def test_load_auth_payload_translates_unreadable_file_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"

    def read_text(self: Path, *, encoding: str) -> str:
        del self, encoding
        msg = "synthetic permission error"
        raise OSError(msg)

    monkeypatch.setattr(Path, "read_text", read_text)

    with pytest.raises(CodexCredentialUnavailableError, match="could not be read"):
        payload.load_auth_payload(auth_path)


@pytest.mark.parametrize(
    "metadata",
    [
        {1: "value"},
        {"unsafe": cast("Any", object())},
    ],
)
def test_codex_transport_observation_rejects_unsafe_metadata(metadata: dict[object, object]) -> None:
    with pytest.raises(TypeError, match="metadata"):
        CodexTransportObservation(message="synthetic", metadata=metadata)  # ty: ignore[invalid-argument-type]


def test_codex_transport_result_rejects_inconsistent_output_and_usage_evidence() -> None:
    with pytest.raises(ValueError, match="successful"):
        CodexTransportResult(status=CodexTransportStatus.SUCCESS)
    with pytest.raises(ValueError, match="non-success"):
        CodexTransportResult(status=CodexTransportStatus.TRANSPORT_ERROR, output_text="unexpected")
    with pytest.raises(ValueError, match="successful"):
        CodexUsageResult(status=CodexTransportStatus.SUCCESS)
    with pytest.raises(ValueError, match="non-success"):
        CodexUsageResult(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            evidence=CodexUsageEvidence({"plan_type": "synthetic"}),
        )


def test_codex_usage_evidence_rejects_unsafe_values() -> None:
    with pytest.raises(TypeError, match="bounded scalar"):
        CodexUsageEvidence({"unsafe": cast("Any", object())})
    with pytest.raises(TypeError, match="keys must be strings"):
        CodexUsageEvidence({1: "unsafe"})  # ty: ignore[invalid-argument-type]
