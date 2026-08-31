"""Tests for command-batch serialized output limiting."""

import pytest

from fabrica.features.workspace_command_execution.application.dtos import (
    CommandExecutionOutput,
    CommandExecutionStatus,
    CommandResult,
    ExecutionPolicy,
    RunCommandsResult,
)
from fabrica.features.workspace_command_execution.application.output_limiting import (
    _head_and_tail,
    _stream_caps,
    limit_run_commands_result,
)
from fabrica.features.workspace_command_execution.application.result_formatting import serialize_run_commands_result

SERIALIZED_LIMIT = 1_400


def test_limit_preserves_each_result_and_fairly_retains_escape_heavy_output() -> None:
    result = RunCommandsResult(
        ExecutionPolicy.PARALLEL,
        (
            _result(0, 'first\\n"' * 200),
            _result(1, 'second\\n"' * 200),
        ),
    )

    limited = limit_run_commands_result(result, max_serialized_chars=SERIALIZED_LIMIT, max_command_output_chars=10_000)

    assert len(serialize_run_commands_result(limited)) <= SERIALIZED_LIMIT
    assert [item.index for item in limited.results] == [0, 1]
    assert all(item.output.output_truncated for item in limited.results)
    assert all(item.output.retained_output_chars > 0 for item in limited.results)
    assert limited.batch_output_truncated is True


def test_limit_preserves_untruncated_result_when_the_full_payload_fits() -> None:
    result = RunCommandsResult(ExecutionPolicy.SEQUENTIAL, (_result(0, "short"),))

    limited = limit_run_commands_result(result, max_serialized_chars=10_000, max_command_output_chars=10_000)

    assert limited == result


@pytest.mark.parametrize(("serialized_limit", "command_limit"), [(0, 1), (1, 0)])
def test_limit_rejects_non_positive_output_bounds(serialized_limit: int, command_limit: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        limit_run_commands_result(
            RunCommandsResult(ExecutionPolicy.PARALLEL, (_result(0, "output"),)),
            max_serialized_chars=serialized_limit,
            max_command_output_chars=command_limit,
        )


def test_stream_limiting_preserves_stream_boundaries_and_handles_small_marker_budgets() -> None:
    stdout_cap, stderr_cap = _stream_caps("stdout", "stderr", 9)

    assert (stdout_cap, stderr_cap) == (4, 5)
    assert _stream_caps("", "stderr", 9) == (0, 9)
    assert _stream_caps("stdout", "", 9) == (9, 0)
    assert _head_and_tail("long output", cap=0, total_chars=11) == ""
    assert _head_and_tail("long output", cap=3, total_chars=11) == "\n[."


def _result(index: int, stdout: str) -> CommandResult:
    return CommandResult(
        index=index,
        command_preview=f"command-{index}",
        status=CommandExecutionStatus.EXITED,
        duration_ms=1,
        exit_code=0,
        output=CommandExecutionOutput(
            stdout=stdout,
            total_output_chars=len(stdout),
            retained_output_chars=len(stdout),
        ),
    )
