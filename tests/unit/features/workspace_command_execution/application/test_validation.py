"""Tests for run-commands structural validation."""

import pytest

from fabrica.features.workspace_command_execution.application.dtos import (
    CommandErrorCode,
    CommandExecutionLimits,
    CommandRequest,
    CommandResult,
    ExecutionPolicy,
)
from fabrica.features.workspace_command_execution.application.validation import validate_run_commands_request


def test_normalizes_omitted_execution_to_parallel_and_preserves_request_order() -> None:
    raw_request = {"commands": [{"argv": ["git", "status"]}, {"shell": "echo ok"}]}

    batch = validate_run_commands_request(
        raw_request,
        limits=CommandExecutionLimits(),
    )
    assert batch.execution is ExecutionPolicy.PARALLEL
    assert all(isinstance(item, CommandRequest) for item in batch.entries)
    assert batch.command is not None


def test_returns_command_scoped_invalid_results_before_spawn() -> None:
    raw_request = {
        "commands": [
            {"argv": ["ok"]},
            {"argv": [], "shell": "bad"},
            {"shell": "x" * 6},
        ]
    }
    batch = validate_run_commands_request(
        raw_request,
        limits=CommandExecutionLimits(max_command_input_chars=5),
    )
    assert isinstance(batch.entries[0], CommandRequest)
    assert isinstance(batch.entries[1], CommandResult)
    assert batch.entries[1].error is not None
    assert batch.entries[1].error.code is CommandErrorCode.INVALID_INPUT
    assert isinstance(batch.entries[2], CommandResult)
    assert batch.entries[2].error is not None
    assert batch.entries[2].error.code is CommandErrorCode.COMMAND_INPUT_TOO_LARGE


def test_maps_timeout_limit_and_invalid_command_field_types_to_command_results() -> None:
    batch = validate_run_commands_request(
        {
            "commands": [
                {"argv": ["ok"], "timeout_ms": 6},
                {"argv": "not-an-array"},
                {"shell": None},
            ]
        },
        limits=CommandExecutionLimits(default_command_timeout_ms=5, max_command_timeout_ms=5),
    )

    first, second, third = batch.entries
    assert isinstance(first, CommandResult)
    assert first.error is not None
    assert first.error.code is CommandErrorCode.COMMAND_TIMEOUT_TOO_LARGE
    assert isinstance(second, CommandResult)
    assert second.error is not None
    assert second.error.code is CommandErrorCode.INVALID_INPUT
    assert isinstance(third, CommandResult)
    assert third.error is not None
    assert third.error.code is CommandErrorCode.INVALID_INPUT


def test_rejects_invalid_execution_and_excessive_command_count() -> None:
    with pytest.raises(ValueError, match="execution"):
        validate_run_commands_request(
            {"execution": "other", "commands": [{"argv": ["ok"]}]}, limits=CommandExecutionLimits()
        )
    with pytest.raises(ValueError, match="host batch"):
        validate_run_commands_request(
            {"commands": [{"argv": ["ok"]}, {"argv": ["ok"]}]},
            limits=CommandExecutionLimits(max_commands_per_call=1, max_concurrent_commands=1),
        )


@pytest.mark.parametrize("raw", [{}, {"commands": []}, {"commands": "bad"}, {"commands": [], "unknown": True}])
def test_rejects_invalid_top_level_batch_shapes(raw: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        validate_run_commands_request(raw, limits=CommandExecutionLimits())
