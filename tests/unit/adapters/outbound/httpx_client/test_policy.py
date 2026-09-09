"""Tests for HTTPX retry policy validation."""

from typing import TYPE_CHECKING, cast

import pytest

from fabrica.adapters.outbound.httpx_client import HttpTimeout, RetryPolicy

if TYPE_CHECKING:
    import httpx


def test_rejects_non_http_retry_exception_types() -> None:
    invalid_exception_type = cast("type[httpx.HTTPError]", KeyboardInterrupt)

    with pytest.raises(TypeError, match="retryable_exception_types"):
        RetryPolicy(retryable_exception_types=(invalid_exception_type,))


def test_rejects_zero_retry_budget() -> None:
    with pytest.raises(ValueError, match="total_budget_seconds"):
        RetryPolicy(total_budget_seconds=0.0)


def test_rejects_zero_max_attempts() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)


@pytest.mark.parametrize(
    "field_name",
    [
        "initial_delay_seconds",
        "max_delay_seconds",
        "retry_after_cap_seconds",
        "total_budget_seconds",
    ],
)
def test_rejects_negative_timing_values(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        RetryPolicy(**{field_name: -0.1})  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("initial_delay_seconds", float("nan")),
        ("max_delay_seconds", float("inf")),
        ("retry_after_cap_seconds", float("-inf")),
        ("total_budget_seconds", float("nan")),
    ],
)
def test_rejects_non_finite_timing_values(field_name: str, value: float) -> None:
    with pytest.raises(ValueError, match=field_name):
        RetryPolicy(**{field_name: value})  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("connect_seconds", -0.1),
        ("read_seconds", float("nan")),
        ("write_seconds", float("inf")),
        ("pool_seconds", float("-inf")),
    ],
)
def test_rejects_invalid_timeout_phase_values(field_name: str, value: float) -> None:
    with pytest.raises(ValueError, match=field_name):
        HttpTimeout(**{field_name: value})


@pytest.mark.parametrize("value", [-0.1, float("nan"), float("inf"), float("-inf")])
def test_same_rejects_invalid_timeout_values(value: float) -> None:
    with pytest.raises(ValueError, match="connect_seconds"):
        HttpTimeout.same(value)
