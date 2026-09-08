"""Tests for injected-stream coding-agent terminal host adapters."""

import asyncio
from io import StringIO

import pytest

from fabrica.features.coding_agent_session.adapters.inbound.terminal import (
    TerminalCommandApprovalResolver,
    TerminalPatchApproval,
    TerminalQuestionTransport,
)
from fabrica.features.user_interaction.application.dtos import (
    AnswerSubmission,
    InteractionPublication,
    InteractionQuestion,
    QuestionId,
)
from fabrica.features.workspace_command_execution.application.dtos import (
    CommandExecutionMode,
    CommandRequest,
    PlannedCommand,
)
from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchApprovalPreview,
    PatchChangeSummary,
    PatchDirectoryOutcome,
    PatchDirectoryOutcomeState,
    PatchDirectoryPlannedEffect,
    PatchPlan,
)


class InterruptingInput(StringIO):
    """Injected terminal input that raises an interrupt while being read."""

    def readline(self, size: int = -1, /) -> str:
        """Simulate a Ctrl-C during host input."""
        _ = size
        raise KeyboardInterrupt


def test_question_transport_submits_explicit_option_answer() -> None:
    submissions: list[AnswerSubmission] = []
    cancellations: list[QuestionId] = []

    async def record_submission(submission: AnswerSubmission) -> None:
        submissions.append(submission)

    async def record_cancellation(question_id: QuestionId) -> None:
        cancellations.append(question_id)

    stdout = StringIO()
    publication = InteractionPublication(
        QuestionId("q_question"), InteractionQuestion("Choose a database", ("PostgreSQL", "SQLite"))
    )

    asyncio.run(
        TerminalQuestionTransport(StringIO("2\n"), stdout, record_submission, record_cancellation).publish(publication)
    )

    assert submissions == [AnswerSubmission(QuestionId("q_question"), "SQLite", selected_option=1)]
    assert cancellations == []
    assert (
        stdout.getvalue() == "Question:\nChoose a database\n  1. PostgreSQL\n  2. SQLite\nAnswer (or option number): "
    )


@pytest.mark.parametrize("stdin", [StringIO("\n"), StringIO(""), InterruptingInput()])
def test_question_transport_does_not_invent_answer_on_empty_eof_or_interrupt(stdin: StringIO) -> None:
    submissions: list[AnswerSubmission] = []
    cancellations: list[QuestionId] = []

    async def record_submission(submission: AnswerSubmission) -> None:
        submissions.append(submission)

    async def record_cancellation(question_id: QuestionId) -> None:
        cancellations.append(question_id)

    publication = InteractionPublication(QuestionId("q_question"), InteractionQuestion("Choose", ("One", "Two")))

    asyncio.run(
        TerminalQuestionTransport(stdin, StringIO(), record_submission, record_cancellation).publish(publication)
    )

    assert submissions == []
    assert cancellations == [QuestionId("q_question")]


@pytest.mark.parametrize(
    ("answer", "expected_status"),
    [("y\n", "approved"), ("yes\n", "approved"), ("n\n", "denied"), ("unexpected\n", "denied"), ("", "denied")],
)
def test_command_approval_requires_explicit_yes(answer: str, expected_status: str) -> None:
    stdout = StringIO()

    approved = asyncio.run(TerminalCommandApprovalResolver(StringIO(answer), stdout).resolve(_command()))

    assert approved is (expected_status == "approved")
    assert "Command approval required:" in stdout.getvalue()
    assert "Workspace directory: src" in stdout.getvalue()
    assert "API_TOKEN" not in stdout.getvalue()


def test_command_approval_denies_interruption() -> None:
    assert asyncio.run(TerminalCommandApprovalResolver(InterruptingInput(), StringIO()).resolve(_command())) is False


def test_patch_approval_renders_digest_paths_preview_and_derived_effects_without_unified_diff() -> None:
    plan = _patch_plan()
    stdout = StringIO()

    decision = asyncio.run(TerminalPatchApproval(StringIO("yes\n"), stdout).decide(plan))

    assert decision.approved is True
    assert decision.plan_digest == plan.plan_digest
    assert "Patch approval required:" in stdout.getvalue()
    assert "Affected path: src/new.py" in stdout.getvalue()
    assert "Derived effect: create directory src" in stdout.getvalue()
    assert f"Plan digest: {plan.plan_digest}" in stdout.getvalue()
    assert "@@" not in stdout.getvalue()


@pytest.mark.parametrize("stdin", [StringIO("no\n"), StringIO(""), InterruptingInput()])
def test_patch_approval_denies_non_approval_eof_and_interruption(stdin: StringIO) -> None:
    plan = _patch_plan()

    decision = asyncio.run(TerminalPatchApproval(stdin, StringIO()).decide(plan))

    assert decision.approved is False
    assert decision.plan_digest == plan.plan_digest


def _command() -> PlannedCommand:
    return PlannedCommand(
        index=0,
        request=CommandRequest(
            mode=CommandExecutionMode.ARGV, argv=("uv", "run", "pytest"), cwd="src", timeout_ms=5_000
        ),
        resolved_cwd="src",
        environment={"API_TOKEN": "secret"},
    )


def _patch_plan() -> PatchPlan:
    return PatchPlan(
        plan_digest="sha256:" + "a" * 64,
        actions=(PatchAction(index=0, kind=PatchActionKind.ADD, path="src/new.py", added_lines=("value = 1",)),),
        changes=(PatchChangeSummary(index=0, operation=PatchActionKind.ADD, path="src/new.py"),),
        created_directories=(
            PatchDirectoryOutcome(
                path="src",
                planned_effect=PatchDirectoryPlannedEffect.CREATE_DIRECTORY,
                final_state=PatchDirectoryOutcomeState.NOT_CREATED,
            ),
        ),
        approval_preview=PatchApprovalPreview("add src/new.py"),
    )
