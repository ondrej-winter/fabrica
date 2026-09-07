"""Tests for supervised POSIX apply-patch helper ownership."""

from asyncio import run
from dataclasses import dataclass
from pathlib import Path

import pytest

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
    def __init__(self, outcome: object | None, *, ready: bool | None = None) -> None:
        self.outcome = outcome
        self.ready = outcome is not None if ready is None else ready
        self.closed = False

    def poll(self) -> bool:
        return self.ready

    def recv(self) -> object:
        outcome = self.outcome
        self.ready = False
        return outcome

    def close(self) -> None:
        self.closed = True


class _EofParentConnection(_ParentConnection):
    def recv(self) -> object:
        raise EOFError


class _ChildConnection:
    def close(self) -> None:
        return None


class _RecordingConnection:
    def __init__(self) -> None:
        self.outcomes: list[PatchResult | None] = []
        self.closed = False

    def send(self, result: PatchResult | None) -> None:
        self.outcomes.append(result)

    def close(self) -> None:
        self.closed = True


def test_supervisor_requires_durable_commit_evidence_before_returning_success(monkeypatch, tmp_path: Path) -> None:
    journal = _journal()
    committed = PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=journal.plan_digest,
    )
    parent = _ParentConnection(committed)
    process = _Process(alive=True)
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", lambda **_kwargs: (parent, _ChildConnection()))
    monkeypatch.setattr(helper_process, "load_durable_journal", lambda *_args: journal)

    result = run(
        helper_process.PosixSupervisedPatchMutationAdapter(tmp_path, process_factory=lambda **_kwargs: process).commit(
            _plan(), journal
        )
    )

    assert result.status is PatchResultStatus.INDETERMINATE_COMMIT_STATE
    assert process.started is True
    assert process.terminated is True
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


def test_supervisor_returns_preparation_outcome_with_matching_durable_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    journal = _journal()
    parent = _ParentConnection(None, ready=True)
    process = _Process(alive=False)
    durable = PatchJournalRecord(journal.journal_digest, journal.plan_digest, PatchJournalState.PREPARED)
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", lambda **_kwargs: (parent, _ChildConnection()))
    monkeypatch.setattr(helper_process, "load_durable_journal", lambda *_args: durable)

    adapter = helper_process.PosixSupervisedPatchMutationAdapter(tmp_path, process_factory=lambda **_kwargs: process)
    result = run(adapter._run(helper_process.PatchHelperOperation.PREPARE_FILES, _plan(), journal))  # noqa: SLF001

    assert result is None
    assert parent.closed is True
    assert process.joined is True


def test_supervisor_returns_rollback_outcome_with_matching_durable_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    journal = _journal()
    outcome = _rolled_back(journal)
    parent = _ParentConnection(outcome)
    process = _Process(alive=False)
    durable = PatchJournalRecord(journal.journal_digest, journal.plan_digest, PatchJournalState.ROLLED_BACK)
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", lambda **_kwargs: (parent, _ChildConnection()))
    monkeypatch.setattr(helper_process, "load_durable_journal", lambda *_args: durable)

    adapter = helper_process.PosixSupervisedPatchMutationAdapter(tmp_path, process_factory=lambda **_kwargs: process)
    result = run(adapter._run(helper_process.PatchHelperOperation.ROLL_BACK, None, journal))  # noqa: SLF001

    assert result is outcome
    assert parent.closed is True
    assert process.joined is True


def test_supervisor_rejects_invalid_ipc_outcome_and_closes_helper_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    journal = _journal()
    parent = _ParentConnection("invalid")
    process = _Process(alive=False)
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", lambda **_kwargs: (parent, _ChildConnection()))

    adapter = helper_process.PosixSupervisedPatchMutationAdapter(tmp_path, process_factory=lambda **_kwargs: process)
    result = run(adapter._run(helper_process.PatchHelperOperation.COMMIT, _plan(), journal))  # noqa: SLF001

    assert result is not None
    assert result.status is PatchResultStatus.INDETERMINATE_COMMIT_STATE
    assert parent.closed is True
    assert process.joined is True


def test_supervisor_requires_recovery_when_ipc_closes_before_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    journal = _journal()
    parent = _EofParentConnection(_committed(journal))
    process = _Process(alive=False)
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", lambda **_kwargs: (parent, _ChildConnection()))

    adapter = helper_process.PosixSupervisedPatchMutationAdapter(tmp_path, process_factory=lambda **_kwargs: process)
    result = run(adapter._run(helper_process.PatchHelperOperation.ROLL_BACK, None, journal))  # noqa: SLF001

    assert result is not None
    assert result.status is PatchResultStatus.RECOVERY_REQUIRED
    assert parent.closed is True
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


@pytest.mark.parametrize(
    ("operation", "expected_event"),
    [
        (helper_process.PatchHelperOperation.PREPARE_DIRECTORIES, "prepare_directories"),
        (helper_process.PatchHelperOperation.PREPARE_FILES, "prepare_files"),
        (helper_process.PatchHelperOperation.COMMIT, "commit"),
        (helper_process.PatchHelperOperation.ROLL_BACK, "roll_back"),
    ],
)
def test_helper_reopens_durable_journal_and_dispatches_one_owned_operation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    operation: helper_process.PatchHelperOperation,
    expected_event: str,
) -> None:
    journal = _journal()
    connection = _RecordingConnection()
    events: list[str] = []

    class _DirectoryAdapter:
        def __init__(self, _workspace_root: Path) -> None:
            pass

        async def prepare(self, _plan: PatchPlan, _journal: PatchJournalRecord) -> None:
            events.append("prepare_directories")

    class _CommitAdapter:
        def __init__(self, _workspace_root: Path) -> None:
            pass

        async def prepare(self, _plan: PatchPlan, _journal: PatchJournalRecord) -> None:
            events.append("prepare_files")

        async def commit(self, _plan: PatchPlan, durable_journal: PatchJournalRecord) -> PatchResult:
            events.append("commit")
            return _committed(durable_journal)

        async def roll_back(self, durable_journal: PatchJournalRecord) -> PatchResult:
            events.append("roll_back")
            return _rolled_back(durable_journal)

    monkeypatch.setattr(helper_process, "_load_durable_journal", lambda *_args: journal)
    monkeypatch.setattr(helper_process, "PosixPatchJournalAndPreparationAdapter", _DirectoryAdapter)
    monkeypatch.setattr(helper_process, "PosixPatchCommitAdapter", _CommitAdapter)

    helper_process.run_patch_operation_in_helper(connection, str(tmp_path), operation, _plan(), journal)

    assert events == [expected_event]
    assert connection.closed is True
    if operation in {
        helper_process.PatchHelperOperation.PREPARE_DIRECTORIES,
        helper_process.PatchHelperOperation.PREPARE_FILES,
    }:
        assert connection.outcomes == [None]
    else:
        assert connection.outcomes[0] is not None


def test_helper_requires_matching_durable_journal_before_mutation(tmp_path: Path) -> None:
    journal = _journal()
    connection = _RecordingConnection()

    helper_process.run_patch_operation_in_helper(
        connection,
        str(tmp_path),
        helper_process.PatchHelperOperation.COMMIT,
        _plan(),
        journal,
    )

    assert connection.closed is True
    assert connection.outcomes[0] is not None
    assert connection.outcomes[0].status is PatchResultStatus.RECOVERY_REQUIRED


@pytest.mark.parametrize(
    ("outcome_status", "state", "expected_status"),
    [
        (None, PatchJournalState.PREPARED, None),
        (PatchResultStatus.COMMITTED, PatchJournalState.COMMITTED, None),
        (PatchResultStatus.COMMIT_FAILED_ROLLED_BACK, PatchJournalState.ROLLED_BACK, None),
        (PatchResultStatus.COMMITTED, PatchJournalState.PREPARED, PatchResultStatus.INDETERMINATE_COMMIT_STATE),
    ],
)
def test_terminal_evidence_requires_the_expected_durable_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    outcome_status: PatchResultStatus | None,
    state: PatchJournalState,
    expected_status: PatchResultStatus | None,
) -> None:
    journal = _journal()
    durable = PatchJournalRecord(journal.journal_digest, journal.plan_digest, state)
    monkeypatch.setattr(helper_process, "load_durable_journal", lambda *_args: durable)
    outcome = (
        None
        if outcome_status is None
        else _committed(journal)
        if outcome_status is PatchResultStatus.COMMITTED
        else _rolled_back(journal)
    )

    result = helper_process._validate_terminal_evidence(  # noqa: SLF001
        tmp_path,
        helper_process.PatchHelperOperation.COMMIT,
        journal,
        outcome,
    )

    if expected_status is None:
        assert result is None
    else:
        assert result is not None
        assert result.status is expected_status


def test_durable_journal_and_plan_validation_rejects_missing_or_mismatched_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    journal = _journal()
    monkeypatch.setattr(helper_process, "load_durable_journal", lambda *_args: None)
    assert helper_process._load_durable_journal(tmp_path, journal) is None  # noqa: SLF001

    mismatched = PatchJournalRecord(journal.journal_digest, "sha256:" + "c" * 64, PatchJournalState.PREPARED)
    monkeypatch.setattr(helper_process, "load_durable_journal", lambda *_args: mismatched)
    assert helper_process._load_durable_journal(tmp_path, journal) is None  # noqa: SLF001

    with pytest.raises(ValueError, match="requires an approved patch plan"):
        helper_process._required_plan(None)  # noqa: SLF001


def _journal() -> PatchJournalRecord:
    return PatchJournalRecord(
        journal_digest=SHA256_JOURNAL,
        plan_digest=SHA256_PLAN,
        state=PatchJournalState.PREPARED,
    )


def _plan() -> PatchPlan:
    return PatchPlan(plan_digest=SHA256_PLAN)


def _committed(journal: PatchJournalRecord) -> PatchResult:
    return PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=journal.plan_digest,
    )


def _rolled_back(journal: PatchJournalRecord) -> PatchResult:
    error = patch_error("COMMIT_FAILED_ROLLED_BACK")
    return PatchResult(
        status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        plan_digest=journal.plan_digest,
        error=error,
    )


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
