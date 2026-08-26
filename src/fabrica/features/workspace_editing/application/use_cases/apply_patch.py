"""Application orchestration for the canonical apply-patch tool."""

from dataclasses import dataclass, field

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
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
    PatchCancellationSignal,
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
    cancellation: PatchCancellationSignal
    parser: ParsePatch = field(default_factory=ParsePatch)
    planner: PlanPatch = field(default_factory=PlanPatch)
    matcher: MatchHunks = field(default_factory=MatchHunks)

    async def apply(self, patch_text: str, limits: PatchLimits | None = None) -> PatchResult:
        """Apply one canonical patch body through application-owned ports."""
        async with self.lease_manager.acquire():
            self.cancellation.throw_if_cancelled()
            capability_result = await self.snapshot_reader.verify_workspace_capabilities()
            if capability_result is not None:
                return capability_result
            return await self._apply_after_capability_check(patch_text, limits)

    async def _apply_after_capability_check(self, patch_text: str, limits: PatchLimits | None) -> PatchResult:
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
        return await self._mutate_approved_plan(planned.plan)

    async def _mutate_approved_plan(self, plan: PatchPlan) -> PatchResult:
        gate_result = await self._evaluate_preparation_gates(plan)
        if gate_result is not None:
            return gate_result

        self.cancellation.throw_if_cancelled()
        journal = await self.journal_store.create(plan)
        staging_result = await self._prepare_visible_effects(plan, journal)
        if staging_result is not None:
            return staging_result
        snapshot_revalidation_result = await self.snapshot_reader.snapshot_plan_inputs(plan)
        if snapshot_revalidation_result is not None:
            rollback_result = await self.committer.roll_back(journal)
            return rollback_result if _is_fatal(rollback_result) else snapshot_revalidation_result
        policy_revalidation_result = await self.policy_evaluator.evaluate(plan)
        if policy_revalidation_result is not None:
            rollback_result = await self.committer.roll_back(journal)
            return rollback_result if _is_fatal(rollback_result) else policy_revalidation_result

        self.cancellation.throw_if_cancelled()
        commit_result = await self.committer.commit(plan, journal)
        if _is_terminal_commit_result(commit_result):
            return _validate_terminal_commit_result(plan, commit_result)
        rollback_result = await self.committer.roll_back(journal)
        return rollback_result if _is_fatal(rollback_result) else commit_result

    async def _evaluate_preparation_gates(self, plan: PatchPlan) -> PatchResult | None:
        for rejection in (
            await self.snapshot_reader.snapshot_plan_inputs(plan),
            await self.policy_evaluator.evaluate(plan),
            await self.approval_requester.request_approval(plan),
        ):
            if rejection is not None:
                return rejection
        return None

    async def _prepare_visible_effects(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        preparation_result = await self.preparation_stager.prepare(plan, journal)
        if preparation_result is not None:
            return preparation_result
        file_staging_result = await self.file_stager.prepare(plan, journal)
        if file_staging_result is None:
            return None
        rollback_result = await self.committer.roll_back(journal)
        return rollback_result if _is_fatal(rollback_result) else file_staging_result

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
