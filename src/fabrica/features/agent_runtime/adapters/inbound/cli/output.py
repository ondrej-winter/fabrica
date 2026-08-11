"""Output formatting for agent-runtime CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunResult,
    LocalAgentRunStatus,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptPolicyEvaluationResult,
    SkillScriptPolicyStatus,
)

EXIT_CODE_BY_STATUS: dict[LocalAgentRunStatus, int] = {
    LocalAgentRunStatus.SUCCESS: 0,
    LocalAgentRunStatus.CONFIGURATION_ERROR: 2,
    LocalAgentRunStatus.MODEL_ERROR: 3,
    LocalAgentRunStatus.UNSUPPORTED_CAPABILITY: 4,
    LocalAgentRunStatus.SAFETY_DENIED: 5,
}

EXIT_CODE_BY_SCRIPT_POLICY_STATUS: dict[SkillScriptPolicyStatus, int] = {
    SkillScriptPolicyStatus.APPROVED: 0,
    SkillScriptPolicyStatus.METADATA_ERROR: 2,
    SkillScriptPolicyStatus.UNSUPPORTED: 4,
    SkillScriptPolicyStatus.DENIED: 5,
    SkillScriptPolicyStatus.POLICY_VIOLATION: 5,
}

EXIT_CODE_BY_SCRIPT_EXECUTION_STATUS: dict[SkillScriptExecutionStatus, int] = {
    SkillScriptExecutionStatus.SUCCESS: 0,
    SkillScriptExecutionStatus.ADAPTER_ERROR: 3,
    SkillScriptExecutionStatus.UNSUPPORTED: 4,
    SkillScriptExecutionStatus.POLICY_DENIED: 5,
    SkillScriptExecutionStatus.EXECUTION_FAILED: 6,
    SkillScriptExecutionStatus.TIMED_OUT: 7,
}

MAX_OUTPUT_LINE_CHARS = 4_000


def write_run_result(result: LocalAgentRunResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a local runtime result and return the matching process exit code."""
    if result.output_text:
        _write_line(stdout, result.output_text)

    if not result.succeeded:
        _write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = _format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            _write_line(stderr, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_STATUS[result.status]


def write_script_policy_result(result: SkillScriptPolicyEvaluationResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a selected script policy result and return the matching exit code."""
    stream = stdout if result.approved else stderr
    _write_line(stream, f"status: {result.status.value}")

    for observation in result.observations:
        metadata = _format_metadata(observation.metadata)
        suffix = f" {metadata}" if metadata else ""
        _write_line(stream, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_SCRIPT_POLICY_STATUS[result.status]


def write_script_execution_result(result: SkillScriptExecutionResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a selected script execution result and return the matching exit code."""
    if result.stdout.text:
        _write_line(stdout, result.stdout.text)
    if result.stderr.text:
        _write_line(stderr, result.stderr.text)

    stream = stdout if result.succeeded else stderr
    _write_line(stream, f"status: {result.status.value}")
    if result.exit_code is not None:
        _write_line(stream, f"exit_code: {result.exit_code}")
    if result.stdout.truncated:
        _write_line(stream, f"stdout: truncated max_chars={result.stdout.max_chars}")
    if result.stderr.truncated:
        _write_line(stream, f"stderr: truncated max_chars={result.stderr.max_chars}")

    for observation in result.observations:
        metadata = _format_metadata(observation.metadata)
        suffix = f" {metadata}" if metadata else ""
        _write_line(stream, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_SCRIPT_EXECUTION_STATUS[result.status]


def _write_line(stream: TextIO, text: str) -> None:
    bounded = _bound_text(text)
    stream.write(bounded)
    if not bounded.endswith("\n"):
        stream.write("\n")


def _format_metadata(metadata: Mapping[str, object]) -> str:
    if not metadata:
        return ""
    return " ".join(f"{key}={_bound_text(str(value))}" for key, value in sorted(metadata.items()))


def _bound_text(text: str) -> str:
    if len(text) <= MAX_OUTPUT_LINE_CHARS:
        return text
    return f"{text[:MAX_OUTPUT_LINE_CHARS]}...<truncated>"


__all__ = [
    "write_run_result",
    "write_script_execution_result",
    "write_script_policy_result",
]
