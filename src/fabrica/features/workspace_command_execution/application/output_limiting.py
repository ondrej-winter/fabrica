"""Fair serialized-result output limiting for workspace command execution."""

from dataclasses import replace

from fabrica.features.workspace_command_execution.application.dtos import (
    CommandExecutionOutput,
    RunCommandsResult,
)
from fabrica.features.workspace_command_execution.application.result_formatting import serialize_run_commands_result

_ALLOCATION_STEP_CHARS = 256


def limit_run_commands_result(
    result: RunCommandsResult,
    *,
    max_serialized_chars: int,
    max_command_output_chars: int,
) -> RunCommandsResult:
    """Retain all result metadata while fitting separate output streams into JSON budget."""
    if max_serialized_chars < 1 or max_command_output_chars < 1:
        msg = "output limits must be positive"
        raise ValueError(msg)

    caps = [min(command.output.retained_output_chars, max_command_output_chars) for command in result.results]
    limited = _with_output_caps(result, caps)
    if len(serialize_run_commands_result(limited)) <= max_serialized_chars and limited == result:
        return result

    caps = [0] * len(result.results)
    limited = _with_output_caps(result, caps)
    if len(serialize_run_commands_result(limited)) > max_serialized_chars:
        msg = "serialized result metadata exceeds the configured output bound"
        raise ValueError(msg)

    while True:
        advanced = False
        for index, command_result in enumerate(result.results):
            maximum = min(command_result.output.retained_output_chars, max_command_output_chars)
            proposed = min(maximum, caps[index] + _ALLOCATION_STEP_CHARS)
            if proposed == caps[index]:
                continue
            candidate_caps = [*caps]
            candidate_caps[index] = proposed
            candidate = _with_output_caps(result, candidate_caps)
            if len(serialize_run_commands_result(candidate)) <= max_serialized_chars:
                caps = candidate_caps
                limited = candidate
                advanced = True
        if not advanced:
            return limited


def _with_output_caps(result: RunCommandsResult, caps: list[int]) -> RunCommandsResult:
    limited_results = tuple(
        replace(command_result, output=_limit_output(command_result.output, cap))
        for command_result, cap in zip(result.results, caps, strict=True)
    )
    return RunCommandsResult(
        execution=result.execution,
        results=limited_results,
        batch_output_truncated=any(item.output.output_truncated for item in limited_results),
    )


def _limit_output(output: CommandExecutionOutput, cap: int) -> CommandExecutionOutput:
    retained_chars = output.retained_output_chars
    if retained_chars <= cap:
        return output
    stdout_cap, stderr_cap = _stream_caps(output.stdout, output.stderr, cap)
    stdout = _head_and_tail(output.stdout, cap=stdout_cap, total_chars=output.total_output_chars)
    stderr = _head_and_tail(output.stderr, cap=stderr_cap, total_chars=output.total_output_chars)
    return CommandExecutionOutput(
        stdout=stdout,
        stderr=stderr,
        output_truncated=True,
        total_output_chars=output.total_output_chars,
        retained_output_chars=len(stdout) + len(stderr),
    )


def _stream_caps(stdout: str, stderr: str, cap: int) -> tuple[int, int]:
    if not stdout:
        return 0, cap
    if not stderr:
        return cap, 0
    stdout_cap = round(cap * len(stdout) / (len(stdout) + len(stderr)))
    return stdout_cap, cap - stdout_cap


def _head_and_tail(text: str, *, cap: int, total_chars: int) -> str:
    if cap == 0:
        return ""
    marker = f"\n[... output truncated: {total_chars} characters total ...]\n"
    if cap <= len(marker):
        return marker[:cap]
    remaining = cap - len(marker)
    head_chars = remaining // 2
    return text[:head_chars] + marker + text[-(remaining - head_chars) :]


__all__ = ["limit_run_commands_result"]
