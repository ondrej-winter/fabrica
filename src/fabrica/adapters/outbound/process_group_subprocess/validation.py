"""Validation for process-group command inputs."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def validated_argv(argv: Sequence[str]) -> list[str]:
    """Validate and materialize an explicit command argv sequence."""
    if isinstance(argv, str):
        msg = "argv must be a sequence of arguments, not a string"
        raise TypeError(msg)
    argv_list = list(argv)
    if not argv_list:
        msg = "argv must include an executable"
        raise ValueError(msg)
    for index, argument in enumerate(argv_list):
        if not isinstance(argument, str):
            msg = f"argv[{index}] must be a string"
            raise TypeError(msg)
        if "\x00" in argument:
            msg = f"argv[{index}] must not contain NUL bytes"
            raise ValueError(msg)
    if not argv_list[0]:
        msg = "argv executable must not be empty"
        raise ValueError(msg)
    return argv_list


def ensure_positive_finite_duration(value: float, *, field_name: str) -> None:
    """Reject non-positive and non-finite process durations."""
    if value <= 0 or not math.isfinite(value):
        msg = f"{field_name} must be positive and finite"
        raise ValueError(msg)
