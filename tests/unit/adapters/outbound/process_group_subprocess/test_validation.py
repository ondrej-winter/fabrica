"""Tests for process-group subprocess input validation."""

import math
from typing import TYPE_CHECKING, cast

import pytest

from fabrica.adapters.outbound.process_group_subprocess.validation import (
    ensure_positive_finite_duration,
    validated_argv,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def test_validated_argv_materializes_valid_argument_sequence() -> None:
    assert validated_argv(("tool", "--version")) == ["tool", "--version"]


@pytest.mark.parametrize(
    ("argv", "expected_error", "message"),
    [
        ((), ValueError, "executable"),
        ("tool", TypeError, "sequence"),
        (("",), ValueError, "executable"),
        (("tool", "bad\x00arg"), ValueError, "NUL"),
        (("tool", 1), TypeError, r"argv\[1\]"),
    ],
)
def test_validated_argv_rejects_malformed_commands(
    argv: object,
    expected_error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(expected_error, match=message):
        validated_argv(cast("Sequence[str]", argv))


@pytest.mark.parametrize("value", [0.0, -1.0, math.inf, math.nan])
def test_ensure_positive_finite_duration_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        ensure_positive_finite_duration(value, field_name="timeout_seconds")


def test_ensure_positive_finite_duration_accepts_positive_finite_value() -> None:
    ensure_positive_finite_duration(0.1, field_name="timeout_seconds")
