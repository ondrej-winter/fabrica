"""Bounded output formatting for the local agent runtime CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fabrica.features.developer_workflow.application.dtos import (
        CommitMessageWorkflowResult,
        ConfirmedCommitWorkflowResult,
    )

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunResult,
    LocalAgentRunStatus,
    ModelCostEvidence,
    ModelUsageEvidence,
    ModelUsageObservation,
    SafeRuntimeMetadataValue,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptPolicyEvaluationResult,
    SkillScriptPolicyStatus,
)
from fabrica.features.developer_workflow.application.dtos import DeveloperWorkflowStatus

MAX_OUTPUT_LINE_CHARS = 4_000

EXIT_CODE_BY_STATUS: dict[LocalAgentRunStatus, int] = {
    LocalAgentRunStatus.SUCCESS: 0,
    LocalAgentRunStatus.CONFIGURATION_ERROR: 2,
    LocalAgentRunStatus.MODEL_ERROR: 3,
    LocalAgentRunStatus.UNSUPPORTED_CAPABILITY: 4,
    LocalAgentRunStatus.SAFETY_DENIED: 5,
}

EXIT_CODE_BY_DEVELOPER_WORKFLOW_STATUS: dict[DeveloperWorkflowStatus, int] = {
    DeveloperWorkflowStatus.SUCCESS: 0,
    DeveloperWorkflowStatus.CONFIGURATION_ERROR: 2,
    DeveloperWorkflowStatus.MODEL_ERROR: 3,
    DeveloperWorkflowStatus.UNSUPPORTED_CAPABILITY: 4,
    DeveloperWorkflowStatus.SAFETY_DENIED: 5,
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
        _write_line(stdout, result.output_text)

    if not result.succeeded:
        _write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = _format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            _write_line(stderr, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_STATUS[result.status]


def write_developer_workflow_result(result: CommitMessageWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a developer workflow result and return the matching process exit code."""
    if result.output_text:
        _write_line(stdout, result.output_text)

    if not result.succeeded:
        _write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = _format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            _write_line(stderr, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_DEVELOPER_WORKFLOW_STATUS[result.status]


def write_model_evidence_report(
    *,
    usage_evidence: tuple[ModelUsageEvidence, ...],
    cost_evidence: tuple[ModelCostEvidence, ...],
    stdout: TextIO,
    include_usage: bool,
    include_prices: bool,
) -> None:
    """Write requested model usage and pricing evidence after command output."""
    if include_usage:
        _write_line(stdout, "Usage evidence:")
        if usage_evidence:
            for evidence in usage_evidence:
                _write_line(stdout, f"- {_format_usage_evidence(evidence)}")
        else:
            _write_line(stdout, "- unavailable")

    if include_prices:
        _write_line(stdout, "Pricing evidence:")
        if cost_evidence:
            for evidence in cost_evidence:
                _write_line(stdout, f"- {_format_cost_evidence(evidence)}")
        else:
            _write_line(stdout, "- unavailable")


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


def write_confirmed_commit_result(result: ConfirmedCommitWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a confirmed commit workflow result and return the matching process exit code."""
    if result.output_text:
        _write_line(stdout, result.output_text)

    if not result.succeeded:
        _write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = _format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            _write_line(stderr, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_DEVELOPER_WORKFLOW_STATUS[result.status]


def _write_line(stream: TextIO, text: str) -> None:
    bounded = _bound_text(text)
    stream.write(bounded)
    if not bounded.endswith("\n"):
        stream.write("\n")


def _format_metadata(metadata: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    if not metadata:
        return ""
    return " ".join(f"{key}={_bound_text(str(value))}" for key, value in sorted(metadata.items()))


def _format_usage_evidence(evidence: ModelUsageEvidence) -> str:
    fields = [
        f"provider={evidence.provider}",
        f"status={evidence.status.value}",
        f"source={evidence.source.value}",
        f"confidence={evidence.confidence.value}",
    ]
    if evidence.model is not None:
        fields.append(f"model={evidence.model}")
    fields.extend(_format_token_fields(evidence))
    if evidence.quota is not None:
        fields.extend(_present_fields(evidence.quota, ("limit", "remaining", "reset_at", "window_seconds")))
    fields.extend(_format_observation_messages(evidence.observations))
    return " ".join(fields)


def _format_cost_evidence(evidence: ModelCostEvidence) -> str:
    fields = [
        f"status={evidence.pricing_status.value}",
        f"source={evidence.source.value}",
        f"confidence={evidence.confidence.value}",
    ]
    if evidence.estimated_amount is not None and evidence.currency is not None:
        fields.append(f"estimated_amount={evidence.estimated_amount}")
        fields.append(f"currency={evidence.currency}")
    fields.extend(_format_observation_messages(evidence.observations))
    return " ".join(fields)


def _format_token_fields(evidence: ModelUsageEvidence) -> list[str]:
    return _present_fields(
        evidence.tokens,
        ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"),
    )


def _present_fields(value: object, names: tuple[str, ...]) -> list[str]:
    return [f"{name}={field_value}" for name in names if (field_value := getattr(value, name)) is not None]


def _format_observation_messages(observations: tuple[ModelUsageObservation, ...]) -> list[str]:
    return [f"observation={_bound_text(observation.message)!r}" for observation in observations]


def _bound_text(text: str) -> str:
    if len(text) <= MAX_OUTPUT_LINE_CHARS:
        return text
    return f"{text[:MAX_OUTPUT_LINE_CHARS]}...<truncated>"
