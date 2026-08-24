"""Tests for apply-patch authorization adapters."""

import asyncio

from fabrica.features.workspace_editing.adapters.outbound.authorization import (
    InProcessPatchMutationLeaseManager,
    PatchApprovalDecision,
    StaticPatchApprovalRequester,
    WorkspacePatchPolicyEvaluator,
)
from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchApprovalPreview,
    PatchPlan,
)

PLAN_DIGEST = "sha256:" + "1" * 64
STALE_DIGEST = "sha256:" + "2" * 64


def test_policy_denies_git_stage_and_journal_paths_without_mutation() -> None:
    evaluator = WorkspacePatchPolicyEvaluator()

    git_result = asyncio.run(
        evaluator.evaluate(_plan(PatchAction(index=0, kind=PatchActionKind.UPDATE, path=".git/config")))
    )
    stage_result = asyncio.run(
        evaluator.evaluate(_plan(PatchAction(index=0, kind=PatchActionKind.ADD, path=".fabrica/apply-patch/stage/tmp")))
    )
    journal_result = asyncio.run(
        evaluator.evaluate(_plan(PatchAction(index=0, kind=PatchActionKind.ADD, path=".fabrica/apply-patch/journal/1")))
    )

    assert git_result is not None
    assert git_result.error is not None
    assert git_result.error.code == "PROTECTED_PATH_DENIED"
    assert stage_result is not None
    assert stage_result.error is not None
    assert stage_result.error.code == "PROTECTED_PATH_DENIED"
    assert journal_result is not None
    assert journal_result.error is not None
    assert journal_result.error.code == "PROTECTED_PATH_DENIED"


def test_policy_allows_unprotected_workspace_paths() -> None:
    result = asyncio.run(
        WorkspacePatchPolicyEvaluator().evaluate(
            _plan(PatchAction(index=0, kind=PatchActionKind.UPDATE, path="src/app.py"))
        )
    )

    assert result is None


def test_policy_denies_protected_move_destination_without_mutation() -> None:
    result = asyncio.run(
        WorkspacePatchPolicyEvaluator().evaluate(
            _plan(
                PatchAction(
                    index=0,
                    kind=PatchActionKind.MOVE,
                    path="src/app.py",
                    destination_path=".git/app.py",
                )
            )
        )
    )

    assert result is not None
    assert result.error is not None
    assert result.error.code == "PROTECTED_PATH_DENIED"


def test_approval_accepts_only_matching_plan_digest() -> None:
    async def approve(plan: PatchPlan) -> PatchApprovalDecision:
        return PatchApprovalDecision(approved=True, plan_digest=plan.plan_digest)

    result = asyncio.run(StaticPatchApprovalRequester(approve).request_approval(_plan()))

    assert result is None


def test_approval_rejects_stale_denied_and_timeout_decisions() -> None:
    async def stale(_plan: PatchPlan) -> PatchApprovalDecision:
        return PatchApprovalDecision(approved=True, plan_digest=STALE_DIGEST)

    async def deny(plan: PatchPlan) -> PatchApprovalDecision:
        return PatchApprovalDecision(approved=False, plan_digest=plan.plan_digest, reason="not safe")

    async def time_out(_plan: PatchPlan) -> PatchApprovalDecision:
        await asyncio.sleep(0.05)
        return PatchApprovalDecision(approved=True, plan_digest=PLAN_DIGEST)

    stale_result = asyncio.run(StaticPatchApprovalRequester(stale).request_approval(_plan()))
    denied_result = asyncio.run(StaticPatchApprovalRequester(deny).request_approval(_plan()))
    timeout_result = asyncio.run(
        StaticPatchApprovalRequester(time_out, timeout_seconds=0.001).request_approval(_plan())
    )

    assert stale_result is not None
    assert stale_result.error is not None
    assert stale_result.error.code == "STALE_PLAN"
    assert denied_result is not None
    assert denied_result.error is not None
    assert denied_result.error.code == "APPROVAL_DENIED"
    assert timeout_result is not None
    assert timeout_result.error is not None
    assert timeout_result.error.code == "APPROVAL_TIMEOUT"


def test_approval_rejects_missing_preview_without_calling_host() -> None:
    called = False

    async def approve(plan: PatchPlan) -> PatchApprovalDecision:
        nonlocal called
        called = True
        return PatchApprovalDecision(approved=True, plan_digest=plan.plan_digest)

    result = asyncio.run(StaticPatchApprovalRequester(approve).request_approval(PatchPlan(plan_digest=PLAN_DIGEST)))

    assert result is not None
    assert result.error is not None
    assert result.error.code == "APPROVAL_DENIED"
    assert called is False


def test_in_process_lease_serializes_calls_and_releases_after_cancellation() -> None:
    async def scenario() -> tuple[list[str], bool]:
        manager = InProcessPatchMutationLeaseManager()
        events: list[str] = []
        entered_second = asyncio.Event()

        async def first_holder() -> None:
            async with manager.acquire(plan_digest=PLAN_DIGEST):
                events.append("first-entered")
                await asyncio.sleep(10)

        async def second_holder() -> None:
            async with manager.acquire(plan_digest=PLAN_DIGEST):
                events.append("second-entered")
                entered_second.set()

        first_task = asyncio.create_task(first_holder())
        await asyncio.sleep(0)
        second_task = asyncio.create_task(second_holder())
        await asyncio.sleep(0)
        first_task.cancel()
        try:
            await first_task
        except asyncio.CancelledError:
            events.append("first-cancelled")
        await asyncio.wait_for(entered_second.wait(), timeout=1)
        await second_task
        async with manager.acquire(plan_digest=PLAN_DIGEST):
            reacquired = True
        return events, reacquired

    events, reacquired = asyncio.run(scenario())

    assert events[0] == "first-entered"
    assert set(events[1:]) == {"first-cancelled", "second-entered"}
    assert reacquired is True


def _plan(action: PatchAction | None = None) -> PatchPlan:
    return PatchPlan(
        plan_digest=PLAN_DIGEST,
        actions=(action,) if action is not None else (),
        approval_preview=PatchApprovalPreview("Apply patch plan:\n- update src/app.py"),
    )
