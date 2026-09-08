"""Tests for coding-agent-session application DTOs."""

from pathlib import Path

import pytest

from fabrica.features.agent_runtime.application.dtos import ToolLoopRunResult, ToolLoopRunStatus
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionResult,
    CodingAgentSessionRuntimeResult,
    MutationDisposition,
    MutationDispositionStatus,
    MutationGateEvidence,
    SessionStatus,
)


def test_session_command_requires_an_absolute_workspace_and_non_empty_prompt() -> None:
    """Reject command inputs that cannot safely identify a session workspace."""
    with pytest.raises(ValueError, match="canonical and absolute"):
        CodingAgentSessionCommand(workspace_root=Path("relative-workspace"), prompt="Inspect")
    with pytest.raises(ValueError, match="prompt must not be empty"):
        CodingAgentSessionCommand(workspace_root=Path("/workspace"), prompt=" \n ")


def test_session_command_copies_selected_context_collections() -> None:
    """Freeze caller-owned selected-context collections at the application boundary."""
    selected_skills: list[object] = []
    command = CodingAgentSessionCommand(
        workspace_root=Path("/workspace"),
        prompt="Inspect",
        selected_skills=selected_skills,  # ty: ignore[invalid-argument-type]
    )
    selected_skills.append(object())

    assert command.selected_skills == ()


def test_mutation_disposition_requires_apply_patch_evidence_for_applied_edits() -> None:
    """Prevent rendering an edit as applied without the authoritative tool evidence."""
    with pytest.raises(ValueError, match="requires apply_patch evidence"):
        MutationDisposition(MutationDispositionStatus.APPLIED)
    with pytest.raises(ValueError, match="cannot name tools"):
        MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED, ("apply_patch",))


def test_disabled_mutation_gate_cannot_report_an_applied_edit() -> None:
    """Keep failed startup mutation capability fail-closed in final evidence."""
    with pytest.raises(ValueError, match="disabled mutation gate"):
        CodingAgentSessionRuntimeResult(
            tool_loop_result=ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS),
            mutation_gate=MutationGateEvidence(mutation_enabled=False, reason="recovery required"),
            mutation_disposition=MutationDisposition(MutationDispositionStatus.APPLIED, ("apply_patch",)),
        )


def test_final_result_rejects_applied_or_read_only_status_contradictions() -> None:
    """Reject final states that could falsely report mutation results."""
    enabled_runtime_result = CodingAgentSessionRuntimeResult(
        tool_loop_result=ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS),
        mutation_gate=MutationGateEvidence(mutation_enabled=True),
        mutation_disposition=MutationDisposition(MutationDispositionStatus.APPLIED, ("apply_patch",)),
    )
    with pytest.raises(ValueError, match="only by a completed session"):
        CodingAgentSessionResult(status=SessionStatus.FAILED, runtime_result=enabled_runtime_result)
    no_mutation_runtime_result = CodingAgentSessionRuntimeResult(
        tool_loop_result=ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS),
        mutation_gate=MutationGateEvidence(mutation_enabled=True),
        mutation_disposition=MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED),
    )
    with pytest.raises(ValueError, match="requires a disabled mutation gate"):
        CodingAgentSessionResult(status=SessionStatus.COMPLETED_READ_ONLY, runtime_result=no_mutation_runtime_result)
