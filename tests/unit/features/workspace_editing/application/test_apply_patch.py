"""Tests for apply-patch application orchestration."""

from asyncio import run
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import Self

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchExecutionContext,
    PatchExecutionPhase,
    PatchJournalRecord,
    PatchJournalState,
    PatchMutationGuarantee,
    PatchPathEvidence,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from fabrica.features.workspace_editing.application.text_snapshot import decode_patch_text
from fabrica.features.workspace_editing.application.use_cases import ApplyPatch, PatchPlanningSnapshot

SHA256_A = "sha256:" + "a" * 64
SHA256_JOURNAL = "sha256:" + "b" * 64
POST_STAGING_SNAPSHOT_CALL = 2


def test_apply_patch_commits_through_ordered_ports() -> None:
    harness = _Harness()
    patch = "*** Begin Patch\n*** Add File: src/new.py\n+value = 1\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result.status is PatchResultStatus.COMMITTED
    assert harness.events == [
        "lease_enter",
        "capability",
        "snapshot",
        "snapshot_plan_inputs",
        "policy",
        "approval",
        "journal_create",
        "prepare_directories",
        "prepare_files",
        "snapshot_plan_inputs",
        "policy",
        "commit",
        "lease_exit",
    ]
    assert harness.committed_plan is not None
    assert harness.committed_plan.actions[0].added_lines == ("value = 1",)


def test_apply_patch_matches_update_hunks_before_planning_and_staging() -> None:
    harness = _Harness(text_by_path={"src/app.py": b"old = 1\n"})
    patch = "*** Begin Patch\n*** Update File: src/app.py\n@@\n-old = 1\n+new = 2\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result.status is PatchResultStatus.COMMITTED
    assert harness.committed_plan is not None
    assert harness.committed_plan.actions[0].added_lines == ("new = 2",)


def test_apply_patch_returns_policy_rejection_before_journaling() -> None:
    rejection = _rejected("PROTECTED_PATH_DENIED", "protected path")
    harness = _Harness(policy_result=rejection)
    patch = "*** Begin Patch\n*** Add File: src/new.py\n+value = 1\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result is rejection
    assert "journal_create" not in harness.events
    assert result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION


def test_apply_patch_rolls_back_preparation_when_file_staging_rejects() -> None:
    staging_rejection = _rejected("STALE_PLAN", "stale during staging")
    harness = _Harness(file_staging_result=staging_rejection)
    patch = "*** Begin Patch\n*** Add File: src/new.py\n+value = 1\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result is staging_rejection
    assert harness.events[-4:] == ["prepare_directories", "prepare_files", "rollback", "lease_exit"]


def test_apply_patch_revalidates_policy_after_staging_before_commit() -> None:
    policy_rejection = _rejected("PROTECTED_PATH_DENIED", "policy changed before commit")
    harness = _Harness(post_staging_policy_result=policy_rejection)
    patch = "*** Begin Patch\n*** Add File: src/new.py\n+value = 1\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result is policy_rejection
    assert harness.events[-6:] == [
        "prepare_directories",
        "prepare_files",
        "snapshot_plan_inputs",
        "policy",
        "rollback",
        "lease_exit",
    ]
    assert "commit" not in harness.events


def test_apply_patch_revalidates_snapshot_after_staging_before_commit() -> None:
    snapshot_rejection = _rejected("STALE_PLAN", "workspace changed after staging")
    harness = _Harness(post_staging_snapshot_result=snapshot_rejection)
    patch = "*** Begin Patch\n*** Add File: src/new.py\n+value = 1\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result is snapshot_rejection
    assert harness.events[-4:] == ["prepare_files", "snapshot_plan_inputs", "rollback", "lease_exit"]
    assert "commit" not in harness.events


def test_apply_patch_reports_indeterminate_state_when_terminal_commit_result_has_wrong_plan_digest() -> None:
    harness = _Harness(commit_result_plan_digest="sha256:" + "c" * 64)
    patch = "*** Begin Patch\n*** Add File: src/new.py\n+value = 1\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result.status is PatchResultStatus.INDETERMINATE_COMMIT_STATE
    assert result.mutation_guarantee is PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION
    assert result.error is not None
    assert result.error.code == "INDETERMINATE_COMMIT_STATE"
    assert harness.committed_plan is not None
    assert result.error.metadata["plan_digest"] == harness.committed_plan.plan_digest


def test_apply_patch_returns_capability_rejection_before_parsing() -> None:
    rejection = _rejected("UNSUPPORTED_FILESYSTEM_GUARANTEE", "unsupported")
    harness = _Harness(capability_result=rejection)

    result = run(harness.use_case.apply("not a patch"))

    assert result is rejection
    assert harness.events == ["lease_enter", "capability", "lease_exit"]


def test_apply_patch_rejects_cancellation_before_planning() -> None:
    cancellation = _MutableCancellation(cancelled=True)
    harness = _Harness()

    result = run(harness.use_case.apply(_add_file_patch(), execution=_execution(cancellation)))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "PLANNING_TIMEOUT"
    assert harness.events == ["lease_enter", "lease_exit"]


def test_apply_patch_rolls_back_when_cancelled_after_directory_preparation() -> None:
    cancellation = _MutableCancellation()
    harness = _Harness(preparation_stager_callback=lambda: setattr(cancellation, "cancelled", True))

    result = run(harness.use_case.apply(_add_file_patch(), execution=_execution(cancellation)))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STAGING_TIMEOUT"
    assert harness.events[-3:] == ["prepare_directories", "rollback", "lease_exit"]


def test_apply_patch_returns_parser_rejection_before_snapshot() -> None:
    harness = _Harness()

    result = run(harness.use_case.apply("not a patch"))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "INCOMPLETE_SENTINELS"
    assert harness.events == ["lease_enter", "capability", "lease_exit"]


def test_apply_patch_returns_planning_snapshot_rejection_before_policy() -> None:
    rejection = _rejected("SOURCE_NOT_FOUND", "missing source")
    harness = _Harness(planning_snapshot_result=rejection)
    patch = "*** Begin Patch\n*** Delete File: src/missing.py\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result is rejection
    assert "policy" not in harness.events


def test_apply_patch_returns_planner_rejection_before_policy() -> None:
    harness = _Harness()
    patch = "*** Begin Patch\n*** Add File: src/new.py\n+value = 1\n*** Add File: src/new.py\n+value = 2\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "DESTINATION_COLLISION"
    assert "policy" not in harness.events


def test_apply_patch_returns_hunk_match_rejection_before_planning_snapshot() -> None:
    harness = _Harness(text_by_path={"src/app.py": b"current\n"})
    patch = "*** Begin Patch\n*** Update File: src/app.py\n@@\n-old\n+new\n*** End Patch"

    result = run(harness.use_case.apply(patch))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "HUNK_CONTEXT_NOT_FOUND"
    assert "snapshot" not in harness.events


def test_apply_patch_returns_recoverable_no_mutation_result_when_cancelled_before_planning() -> None:
    harness = _Harness()
    cancellation = _MutableCancellation(cancelled=True)

    result = run(harness.use_case.apply(_add_file_patch(), execution=_execution(cancellation)))

    assert result.status is PatchResultStatus.REJECTED
    assert result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION
    assert result.error is not None
    assert result.error.code == "PLANNING_TIMEOUT"
    assert harness.events == ["lease_enter", "lease_exit"]


def test_apply_patch_returns_recoverable_no_mutation_result_when_planning_deadline_expires() -> None:
    deadline = datetime(2026, 9, 2, tzinfo=UTC)
    harness = _Harness(clock=_FixedClock(datetime(2026, 9, 2, 0, 0, 1, tzinfo=UTC)))

    result = run(
        harness.use_case.apply(_add_file_patch(), execution=_execution(_MutableCancellation(), deadline=deadline))
    )

    assert result.status is PatchResultStatus.REJECTED
    assert result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION
    assert result.error is not None
    assert result.error.code == "PLANNING_TIMEOUT"
    assert harness.events == ["lease_enter", "capability", "lease_exit"]


def test_apply_patch_rolls_back_when_cancelled_after_journaled_preparation() -> None:
    cancellation = _MutableCancellation()
    harness = _Harness(preparation_stager_callback=lambda: setattr(cancellation, "cancelled", True))

    result = run(harness.use_case.apply(_add_file_patch(), execution=_execution(cancellation)))

    assert result.status is PatchResultStatus.REJECTED
    assert result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION
    assert result.error is not None
    assert result.error.code == "STAGING_TIMEOUT"
    assert harness.events[-4:] == ["journal_create", "prepare_directories", "rollback", "lease_exit"]
    assert "prepare_files" not in harness.events


@dataclass(slots=True)
class _Harness:
    text_by_path: dict[str, bytes] = field(default_factory=dict)
    capability_result: PatchResult | None = None
    planning_snapshot_result: PatchPlanningSnapshot | PatchResult | None = None
    post_staging_snapshot_result: PatchResult | None = None
    policy_result: PatchResult | None = None
    post_staging_policy_result: PatchResult | None = None
    file_staging_result: PatchResult | None = None
    preparation_stager_callback: Callable[[], None] | None = None
    clock: _FixedClock = field(default_factory=lambda: _FixedClock(datetime(2026, 9, 2, tzinfo=UTC)))
    commit_result_plan_digest: str | None = None
    events: list[str] = field(default_factory=list)
    committed_plan: PatchPlan | None = None
    snapshot_reader: _SnapshotReader = field(init=False)
    journal_store: _JournalStore = field(init=False)
    committer: _Committer = field(init=False)
    use_case: ApplyPatch = field(init=False)

    def __post_init__(self) -> None:
        self.snapshot_reader = _SnapshotReader(
            self.events,
            self.text_by_path,
            self.capability_result,
            self.planning_snapshot_result,
            self.post_staging_snapshot_result,
        )
        self.journal_store = _JournalStore(self.events)
        self.committer = _Committer(self.events, self)
        self.use_case = ApplyPatch(
            lease_manager=_LeaseManager(self.events),
            snapshot_reader=self.snapshot_reader,
            policy_evaluator=_PolicyEvaluator(self.events, self.policy_result, self.post_staging_policy_result),
            approval_requester=_ApprovalRequester(self.events),
            journal_store=self.journal_store,
            preparation_stager=_Stager(self.events, "prepare_directories", callback=self.preparation_stager_callback),
            file_stager=_Stager(self.events, "prepare_files", self.file_staging_result),
            committer=self.committer,
            clock=self.clock,
        )


@dataclass(slots=True)
class _Lease(AbstractAsyncContextManager["_Lease"]):
    events: list[str]

    async def __aenter__(self) -> Self:
        self.events.append("lease_enter")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.events.append("lease_exit")


@dataclass(slots=True)
class _LeaseManager:
    events: list[str]

    def acquire(self, *, plan_digest: str | None = None) -> _Lease:
        _ = plan_digest
        return _Lease(self.events)


@dataclass(slots=True)
class _SnapshotReader:
    events: list[str]
    text_by_path: dict[str, bytes]
    capability_result: PatchResult | None = None
    planning_snapshot_result: PatchPlanningSnapshot | PatchResult | None = None
    post_staging_snapshot_result: PatchResult | None = None
    snapshot_plan_input_calls: int = 0

    async def verify_workspace_capabilities(self) -> PatchResult | None:
        self.events.append("capability")
        return self.capability_result

    async def snapshot_plan_inputs(self, plan: PatchPlan) -> PatchResult | None:
        _ = plan
        self.events.append("snapshot_plan_inputs")
        self.snapshot_plan_input_calls += 1
        if self.snapshot_plan_input_calls == POST_STAGING_SNAPSHOT_CALL:
            return self.post_staging_snapshot_result
        return None

    async def snapshot_for_planning(self, actions: tuple[PatchAction, ...]) -> PatchPlanningSnapshot | PatchResult:
        self.events.append("snapshot")
        if self.planning_snapshot_result is not None:
            return self.planning_snapshot_result
        evidence = {
            action.path: PatchPathEvidence(action.path, exists=True, content_digest=SHA256_A) for action in actions
        }
        return PatchPlanningSnapshot(evidence_by_path=evidence, existing_directories=frozenset({"", "src"}))

    async def read_text_snapshot(self, path: str):
        return decode_patch_text(self.text_by_path[path])


@dataclass(slots=True)
class _PolicyEvaluator:
    events: list[str]
    result: PatchResult | None = None
    post_staging_result: PatchResult | None = None
    calls: int = 0

    async def evaluate(self, plan: PatchPlan) -> PatchResult | None:
        _ = plan
        self.events.append("policy")
        self.calls += 1
        return self.result if self.calls == 1 else self.post_staging_result


@dataclass(slots=True)
class _ApprovalRequester:
    events: list[str]

    async def request_approval(self, plan: PatchPlan) -> PatchResult | None:
        _ = plan
        self.events.append("approval")
        return None


@dataclass(slots=True)
class _JournalStore:
    events: list[str]

    async def list_incomplete(self) -> tuple[PatchJournalRecord, ...]:
        return ()

    async def create(self, plan: PatchPlan) -> PatchJournalRecord:
        self.events.append("journal_create")
        return PatchJournalRecord(
            journal_digest=SHA256_JOURNAL,
            plan_digest=plan.plan_digest,
            state=PatchJournalState.PLANNED,
        )

    async def transition(self, record: PatchJournalRecord, destination: PatchJournalState) -> PatchJournalRecord:
        return PatchJournalRecord(record.journal_digest, record.plan_digest, destination)


@dataclass(slots=True)
class _Stager:
    events: list[str]
    event: str
    result: PatchResult | None = None
    callback: Callable[[], None] | None = None

    async def prepare(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        _ = plan, journal
        self.events.append(self.event)
        if self.callback is not None:
            self.callback()
        return self.result


@dataclass(slots=True)
class _Committer:
    events: list[str]
    harness: _Harness

    async def commit(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult:
        _ = journal
        self.events.append("commit")
        self.harness.committed_plan = plan
        return PatchResult(
            status=PatchResultStatus.COMMITTED,
            mutation_guarantee=PatchMutationGuarantee.COMMITTED,
            plan_digest=self.harness.commit_result_plan_digest or plan.plan_digest,
            changes=plan.changes,
        )

    async def roll_back(self, journal: PatchJournalRecord) -> PatchResult:
        self.events.append("rollback")
        error = patch_error("COMMIT_FAILED_ROLLED_BACK", message="rolled back")
        return PatchResult(
            status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
            mutation_guarantee=error.mutation_guarantee,
            plan_digest=journal.plan_digest,
            error=error,
        )


@dataclass(slots=True)
class _MutableCancellation:
    cancelled: bool = False

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled


def _execution(cancellation: _MutableCancellation, *, deadline: datetime | None = None) -> PatchExecutionContext:
    deadlines = {} if deadline is None else {PatchExecutionPhase.PLANNING: deadline}
    return PatchExecutionContext(cancellation=cancellation, phase_deadlines=deadlines)


@dataclass(frozen=True, slots=True)
class _FixedClock:
    current: datetime

    def now(self) -> datetime:
        return self.current


def _add_file_patch() -> str:
    return "*** Begin Patch\n*** Add File: src/new.py\n+value = 1\n*** End Patch"


def _rejected(code: str, message: str) -> PatchResult:
    error = patch_error(code, message=message)
    return PatchResult(status=PatchResultStatus.REJECTED, mutation_guarantee=error.mutation_guarantee, error=error)
