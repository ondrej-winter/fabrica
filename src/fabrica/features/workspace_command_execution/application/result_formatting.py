"""Canonical model-visible formatting for workspace command results."""

import json

from fabrica.features.workspace_command_execution.application.dtos import CommandResult, RunCommandsResult


def run_commands_result_payload(result: RunCommandsResult) -> dict[str, object]:
    """Return the stable JSON-compatible payload for one bounded command batch."""
    return {
        "execution": result.execution.value,
        "results": [_command_result_payload(command_result) for command_result in result.results],
        "batch_output_truncated": result.batch_output_truncated,
    }


def serialize_run_commands_result(result: RunCommandsResult) -> str:
    """Serialize a command result with the canonical compact JSON representation."""
    return json.dumps(run_commands_result_payload(result), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _command_result_payload(result: CommandResult) -> dict[str, object]:
    output = result.output
    return {
        "index": result.index,
        "command_preview": result.command_preview,
        "status": result.status.value,
        "success": result.success,
        "exit_code": result.exit_code,
        "signal": result.signal,
        "duration_ms": result.duration_ms,
        "stdout": output.stdout,
        "stderr": output.stderr,
        "output_truncated": output.output_truncated,
        "total_output_chars": output.total_output_chars,
        "retained_output_chars": output.retained_output_chars,
        "stdout_chars": len(output.stdout),
        "stderr_chars": len(output.stderr),
        "error": None if result.error is None else {"code": result.error.code.value, "message": result.error.message},
        "reason": None if result.reason is None else result.reason.value,
    }


__all__ = ["run_commands_result_payload", "serialize_run_commands_result"]
