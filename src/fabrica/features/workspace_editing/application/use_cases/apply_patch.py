"""Application orchestration for the canonical apply-patch tool."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchExecutionContext,
    PatchExecutionPhase,
    PatchJournalRecord,
    PatchLimits,
    PatchMutationGuarantee,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from fabrica.features.workspace_editing.application.ports import (
    PatchApprovalRequester,
    PatchClock,
    PatchCommitter,
    PatchJournalStore,
    PatchMutationLeaseManager,
    PatchPolicyEvaluator,
    PatchStager,
    PatchWorkspaceSnapshotReader,
)
from fabrica.features.workspace_editing.application.text_snapshot import PatchTextDecodingError, PatchTextSnapshot
from fabrica.features.workspace_editing.application.use_cases.match_hunks import MatchHunks
from fabrica.features.workspace_editing.application.use_cases.parse_patch import ParsePatch
from fabrica.features.workspace_editing.application.use_cases.plan_patch import PlanPatch


@dataclass(frozen=True, slots=True)
class _SystemPatchClock:
    """Default UTC clock for hosts that do not provide deterministic deadlines."""

    def now(self) -> datetime:
        """Return the current UTC timestamp."""
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ApplyPatch:
    """Coordinate parsing, planning, approval, journaling, staging, and commit."""

    lease_manager: PatchMutationLeaseManager
    snapshot_reader: PatchWorkspaceSnapshotReader
    policy_evaluator: PatchPolicyEvaluator
    approval_requester: PatchApprovalRequester
    journal_store: PatchJournalStore
    preparation_stager: PatchStager
    file_stager: PatchStager
    committer: PatchCommitter
    clock: PatchClock = field(default_factory=_SystemPatchClock)
    parser: ParsePatch = field(default_factory=ParsePatch)
    planner: PlanPatch = field(default_factory=PlanPatch)
    matcher: MatchHunks = field(default_factory=MatchHunks)

    async def apply(
        self,
        patch_text: str,
        limits: PatchLimits | None = None,
        execution: PatchExecutionContext | None = None,
    ) -> PatchResult:
        """Apply one canonical patch body through application-owned ports."""
        async with self.lease_manager.acquire():
            checkpoint_result = self._checkpoint(PatchExecutionPhase.LEASE, execution)
            if checkpoint_result is not None:
                return checkpoint_result
            capability_result = await self.snapshot_reader.verify_workspace_capabilities()
            if capability_result is not None:
                return capability_result
            return await self._apply_after_capability_check(patch_text, limits, execution)

    async def _apply_after_capability_check(
        self,
        patch_text: str,
        limits: PatchLimits | None,
        execution: PatchExecutionContext | None,
    ) -> PatchResult:
        checkpoint_result = self._checkpoint(PatchExecutionPhase.PLANNING, execution)
        if checkpoint_result is not None:
            return checkpoint_result
        parsed = self.parser.parse(patch_text, limits)
        if parsed.plan is None:
            return parsed.result

        prepared_actions_result = await self._actions_with_complete_payloads(parsed.plan.actions)
        if isinstance(prepared_actions_result, PatchResult):
            return prepared_actions_result

        snapshot_result = await self.snapshot_reader.snapshot_for_planning(prepared_actions_result)
        if isinstance(snapshot_result, PatchResult):
            return snapshot_result

        planned = self.planner.plan(prepared_actions_result, snapshot_result, limits)
        if planned.plan is None:
            return planned.result
        return await self._mutate_approved_plan(planned.plan, execution)

    async def _mutate_approved_plan(self, plan: PatchPlan, execution: PatchExecutionContext | None) -> PatchResult:
        gate_result = await self._evaluate_preparation_gates(plan, execution)
        if gate_result is not None:
            return gate_result

        checkpoint_result = self._checkpoint(PatchExecutionPhase.STAGING, execution)
        if checkpoint_result is not None:
            return checkpoint_result
        journal = await self.journal_store.create(plan)
        staging_result = await self._prepare_visible_effects(plan, journal, execution)
        if staging_result is not None:
            return staging_result
        revalidation_result = await self._revalidate_staged_plan(plan, journal)
        if revalidation_result is not None:
            return revalidation_result
        return await self._commit_plan(plan, journal, execution)

    async def _revalidate_staged_plan(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        snapshot_revalidation_result = await self.snapshot_reader.snapshot_plan_inputs(plan)
        if snapshot_revalidation_result is not None:
            rollback_result = await self.committer.roll_back(journal)
            return rollback_result if _is_fatal(rollback_result) else snapshot_revalidation_result
        policy_revalidation_result = await self.policy_evaluator.evaluate(plan)
        if policy_revalidation_result is not None:
            rollback_result = await self.committer.roll_back(journal)
            return rollback_result if _is_fatal(rollback_result) else policy_revalidation_result
        return None

    async def _commit_plan(
        self,
        plan: PatchPlan,
        journal: PatchJournalRecord,
        execution: PatchExecutionContext | None,
    ) -> PatchResult:
        checkpoint_result = self._checkpoint(PatchExecutionPhase.COMMIT, execution)
        if checkpoint_result is not None:
            return await self._roll_back_after_interruption(journal, checkpoint_result)
        commit_result = await self.committer.commit(plan, journal)
        if _is_terminal_commit_result(commit_result):
            return _validate_terminal_commit_result(plan, commit_result)
        rollback_result = await self.committer.roll_back(journal)
        return rollback_result if _is_fatal(rollback_result) else commit_result

    async def _evaluate_preparation_gates(
        self, plan: PatchPlan, execution: PatchExecutionContext | None
    ) -> PatchResult | None:
        checkpoint_result = self._checkpoint(PatchExecutionPhase.APPROVAL, execution)
        if checkpoint_result is not None:
            return checkpoint_result
        for rejection in (
            await self.snapshot_reader.snapshot_plan_inputs(plan),
            await self.policy_evaluator.evaluate(plan),
            await self.approval_requester.request_approval(plan),
        ):
            if rejection is not None:
                return rejection
        return None

    async def _prepare_visible_effects(
        self,
        plan: PatchPlan,
        journal: PatchJournalRecord,
        execution: PatchExecutionContext | None,
    ) -> PatchResult | None:
        checkpoint_result = self._checkpoint(PatchExecutionPhase.STAGING, execution)
        if checkpoint_result is not None:
            return await self._roll_back_after_interruption(journal, checkpoint_result)
        preparation_result = await self.preparation_stager.prepare(plan, journal)
        if preparation_result is not None:
            return preparation_result
        checkpoint_result = self._checkpoint(PatchExecutionPhase.STAGING, execution)
        if checkpoint_result is not None:
            return await self._roll_back_after_interruption(journal, checkpoint_result)
        file_staging_result = await self.file_stager.prepare(plan, journal)
        if file_staging_result is None:
            return None
        rollback_result = await self.committer.roll_back(journal)
        return rollback_result if _is_fatal(rollback_result) else file_staging_result

    async def _roll_back_after_interruption(
        self, journal: PatchJournalRecord, interruption: PatchResult
    ) -> PatchResult:
        rollback_result = await self.committer.roll_back(journal)
        return rollback_result if _is_fatal(rollback_result) else interruption

    def _checkpoint(
        self,
        phase: PatchExecutionPhase,
        execution: PatchExecutionContext | None,
    ) -> PatchResult | None:
        if execution is None:
            return None
        deadline = execution.deadline_for(phase)
        expired = deadline is not None and self.clock.now() >= deadline
        if not execution.cancellation.is_cancelled and not expired:
            return None
        error_code = (
            "PLANNING_TIMEOUT"
            if phase
            in {
                PatchExecutionPhase.LEASE,
                PatchExecutionPhase.PLANNING,
                PatchExecutionPhase.APPROVAL,
            }
            else "STAGING_TIMEOUT"
        )
        reason = "cancelled" if execution.cancellation.is_cancelled else "deadline expired"
        error = patch_error(error_code, message=f"apply-patch {phase.value} phase {reason}")
        return PatchResult(
            status=PatchResultStatus.REJECTED,
            mutation_guarantee=error.mutation_guarantee,
            error=error,
        )

    async def _actions_with_complete_payloads(
        self, actions: tuple[PatchAction, ...]
    ) -> tuple[PatchAction, ...] | PatchResult:
        prepared: list[PatchAction] = []
        for action in actions:
            if action.kind is PatchActionKind.ADD or not action.hunks:
                prepared.append(action)
                continue
            snapshot_result = await self.snapshot_reader.read_text_snapshot(action.path)
            if isinstance(snapshot_result, PatchResult):
                return snapshot_result
            try:
                matched = self.matcher.match(snapshot_result, action.hunks)
            except PatchTextDecodingError as err:
                return PatchResult(
                    status=PatchResultStatus.REJECTED,
                    mutation_guarantee=err.error.mutation_guarantee,
                    error=err.error,
                )
            if matched.result.status is not PatchResultStatus.COMMITTED:
                return matched.result
            prepared.append(_action_with_payload(action, snapshot_result, matched.lines))
        return tuple(prepared)


def _action_with_payload(action: PatchAction, snapshot: PatchTextSnapshot, lines: tuple[str, ...]) -> PatchAction:
    rendered = snapshot.render(lines)
    rendered_text = rendered.decode("utf-8-sig")
    added_lines = _split_rendered_lines(rendered_text, snapshot)
    return PatchAction(
        index=action.index,
        kind=action.kind,
        path=action.path,
        destination_path=action.destination_path,
        hunks=action.hunks,
        added_lines=added_lines,
    )


def _split_rendered_lines(rendered_text: str, snapshot: PatchTextSnapshot) -> tuple[str, ...]:
    if not rendered_text:
        return ()
    return tuple(rendered_text.removesuffix(snapshot.line_ending_text).split(snapshot.line_ending_text))


def _is_fatal(result: PatchResult) -> bool:
    return result.mutation_guarantee in {
        PatchMutationGuarantee.REVERSIBLE_EFFECTS_RETAINED,
        PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
    }


def _is_terminal_commit_result(result: PatchResult) -> bool:
    return result.status in {
        PatchResultStatus.COMMITTED,
        PatchResultStatus.PARTIAL_COMMIT,
        PatchResultStatus.ROLLBACK_FAILED,
        PatchResultStatus.INDETERMINATE_COMMIT_STATE,
        PatchResultStatus.RECOVERY_REQUIRED,
    }


def _validate_terminal_commit_result(plan: PatchPlan, result: PatchResult) -> PatchResult:
    """Fail closed when terminal adapter evidence is not bound to the approved plan."""
    if result.plan_digest == plan.plan_digest:
        return result
    error = patch_error(
        "INDETERMINATE_COMMIT_STATE",
        message="terminal commit result was not bound to the approved patch plan",
        metadata={"plan_digest": plan.plan_digest},
    )
    return PatchResult(
        status=PatchResultStatus.INDETERMINATE_COMMIT_STATE,
        mutation_guarantee=error.mutation_guarantee,
        plan_digest=plan.plan_digest,
        error=error,
    )


__all__ = ["ApplyPatch"]
