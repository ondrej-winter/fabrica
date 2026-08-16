"""Output formatting for agent-runtime CLI commands."""

from __future__ import annotations

from typing import TextIO

from fabrica.adapters.inbound.cli.rendering import format_metadata, write_line, write_text
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


def write_run_result(result: LocalAgentRunResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a local runtime result and return the matching process exit code."""
    if result.output_text:
        write_text(stdout, result.output_text)

    if not result.succeeded:
        write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            write_line(stderr, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_STATUS[result.status]


def write_script_policy_result(result: SkillScriptPolicyEvaluationResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a selected script policy result and return the matching exit code."""
    stream = stdout if result.approved else stderr
    write_line(stream, f"status: {result.status.value}")
    if result.approved and result.binding is not None:
        write_line(stream, f"approve-script-type: {result.binding.script_type.value}")
        write_line(stream, f"approve-suffix: {result.binding.suffix}")
        write_line(stream, f"approve-byte-size: {result.binding.byte_size}")
        write_line(stream, f"approve-content-digest: {result.binding.content_digest}")

    for observation in result.observations:
        metadata = format_metadata(observation.metadata)
        suffix = f" {metadata}" if metadata else ""
        write_line(stream, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_SCRIPT_POLICY_STATUS[result.status]


def write_script_execution_result(result: SkillScriptExecutionResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a selected script execution result and return the matching exit code."""
    if result.stdout.text:
        write_text(stdout, result.stdout.text)
    if result.stderr.text:
        write_text(stderr, result.stderr.text)

    stream = stdout if result.succeeded else stderr
    write_line(stream, f"status: {result.status.value}")
    if result.exit_code is not None:
        write_line(stream, f"exit_code: {result.exit_code}")
    if result.stdout.truncated:
        write_line(stream, f"stdout: truncated max_chars={result.stdout.max_chars}")
    if result.stderr.truncated:
        write_line(stream, f"stderr: truncated max_chars={result.stderr.max_chars}")

    for observation in result.observations:
        metadata = format_metadata(observation.metadata)
        suffix = f" {metadata}" if metadata else ""
        write_line(stream, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_SCRIPT_EXECUTION_STATUS[result.status]


__all__ = [
    "write_run_result",
    "write_script_execution_result",
    "write_script_policy_result",
]
