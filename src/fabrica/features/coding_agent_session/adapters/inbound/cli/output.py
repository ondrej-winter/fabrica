"""Output formatting for coding-agent-session CLI commands."""

from typing import TextIO

from fabrica.adapters.inbound.cli.rendering import write_line, write_text
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionResult,
    MutationDispositionStatus,
    SessionStatus,
)

EXIT_CODE_BY_SESSION_STATUS: dict[SessionStatus, int] = {
    SessionStatus.COMPLETED: 0,
    SessionStatus.COMPLETED_READ_ONLY: 0,
    SessionStatus.CANCELLED: 130,
    SessionStatus.FAILED: 3,
}


def write_session_result(result: CodingAgentSessionResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write safe terminal evidence and return the stable session exit code."""
    runtime_result = result.runtime_result
    tool_loop_result = runtime_result.tool_loop_result
    if tool_loop_result.output_text:
        write_text(stdout, tool_loop_result.output_text)

    if not runtime_result.mutation_gate.mutation_enabled:
        write_line(stdout, "Mutation: unavailable; session completed read-only.")
        if runtime_result.mutation_gate.reason is not None:
            write_line(stdout, f"Mutation gate: {runtime_result.mutation_gate.reason}")
    write_line(stdout, f"Mutation disposition: {runtime_result.mutation_disposition.status.value}")
    write_line(stdout, f"Session status: {result.status.value}")

    if result.status is SessionStatus.FAILED:
        write_line(stderr, f"tool-loop status: {tool_loop_result.status.value}")
    elif result.status is SessionStatus.CANCELLED:
        write_line(stderr, "session cancelled")
    elif runtime_result.mutation_disposition.status is MutationDispositionStatus.INDETERMINATE:
        write_line(stderr, "warning: mutation result is indeterminate")

    return EXIT_CODE_BY_SESSION_STATUS[result.status]
