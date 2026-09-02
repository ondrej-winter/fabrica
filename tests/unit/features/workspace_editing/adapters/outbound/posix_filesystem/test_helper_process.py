"""Tests for supervised POSIX apply-patch helper ownership."""

from asyncio import run
from dataclasses import dataclass
from pathlib import Path

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import helper_process
from fabrica.features.workspace_editing.application.dtos import (
    PatchJournalRecord,
    PatchJournalState,
    PatchMutationGuarantee,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error

SHA256_PLAN = "sha256:" + "a" * 64
SHA256_JOURNAL = "sha256:" + "b" * 64


@dataclass
class _Process:
    alive: bool
    started: bool = False
    terminated: bool = False
    joined: bool = False

    def start(self) -> None:
        self.started = True

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False

    def join(self) -> None:
        self.joined = True


class _ParentConnection:
    def __init__(self, outcome: object | None) -> None:
        self.outcome = outcome
        self.closed = False

    def poll(self) -> bool:
        return self.outcome is not None

    def recv(self) -> object:
        outcome = self.outcome
        self.outcome = None
        return outcome

    def close(self) -> None:
        self.closed = True


class _ChildConnection:
    def close(self) -> None:
        return None


def test_supervisor_requires_durable_commit_evidence_before_returning_success(monkeypatch, tmp_path: Path) -> None:
    journal = _journal()
    committed = PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=journal.plan_digest,
    )
    parent = _ParentConnection(committed)
    process = _Process(alive=False)
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", lambda **_kwargs: (parent, _ChildConnection()))
    monkeypatch.setattr(helper_process, "load_durable_journal", lambda *_args: journal)

    result = run(
        helper_process.PosixSupervisedPatchMutationAdapter(tmp_path, process_factory=lambda **_kwargs: process).commit(
            _plan(), journal
        )
    )

    assert result.status is PatchResultStatus.INDETERMINATE_COMMIT_STATE
    assert process.started is True
    assert process.joined is True


def test_supervisor_reports_recovery_required_when_helper_exits_without_ipc_outcome(
    monkeypatch, tmp_path: Path
) -> None:
    journal = _journal()
    parent = _ParentConnection(None)
    process = _Process(alive=False)
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", lambda **_kwargs: (parent, _ChildConnection()))

    result = run(
        helper_process.PosixSupervisedPatchMutationAdapter(
            tmp_path, process_factory=lambda **_kwargs: process
        ).roll_back(journal)
    )

    assert result.status is PatchResultStatus.RECOVERY_REQUIRED
    assert result.mutation_guarantee is PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION
    assert process.joined is True


def test_port_shaped_wrappers_delegate_to_the_supervisor() -> None:
    supervisor = _Supervisor()
    plan = _plan()
    journal = _journal()

    directory_result = run(helper_process.PosixSupervisedPatchPreparationAdapter(supervisor).prepare(plan, journal))
    file_result = run(helper_process.PosixSupervisedPatchCommitAdapter(supervisor).prepare(plan, journal))
    commit_result = run(helper_process.PosixSupervisedPatchCommitAdapter(supervisor).commit(plan, journal))
    rollback_result = run(helper_process.PosixSupervisedPatchCommitAdapter(supervisor).roll_back(journal))

    assert directory_result is None
    assert file_result is None
    assert commit_result.status is PatchResultStatus.COMMITTED
    assert rollback_result.status is PatchResultStatus.COMMIT_FAILED_ROLLED_BACK
    assert supervisor.events == ["directories", "files", "commit", "rollback"]


def _journal() -> PatchJournalRecord:
    return PatchJournalRecord(
        journal_digest=SHA256_JOURNAL,
        plan_digest=SHA256_PLAN,
        state=PatchJournalState.PREPARED,
    )


def _plan() -> PatchPlan:
    return PatchPlan(plan_digest=SHA256_PLAN)


class _Supervisor:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def prepare_directories(self, plan: PatchPlan, journal: PatchJournalRecord) -> None:
        _ = plan, journal
        self.events.append("directories")

    async def prepare_files(self, plan: PatchPlan, journal: PatchJournalRecord) -> None:
        _ = plan, journal
        self.events.append("files")

    async def commit(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult:
        _ = plan
        self.events.append("commit")
        return PatchResult(
            status=PatchResultStatus.COMMITTED,
            mutation_guarantee=PatchMutationGuarantee.COMMITTED,
            plan_digest=journal.plan_digest,
        )

    async def roll_back(self, journal: PatchJournalRecord) -> PatchResult:
        self.events.append("rollback")
        error = patch_error("COMMIT_FAILED_ROLLED_BACK")
        return PatchResult(
            status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
            plan_digest=journal.plan_digest,
            error=error,
        )
