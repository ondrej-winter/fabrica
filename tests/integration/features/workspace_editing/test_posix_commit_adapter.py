"""Integration tests for POSIX apply-patch staging and commit."""

import json
import sys
from asyncio import run
from pathlib import Path
from stat import S_IMODE

import pytest

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import (
    PosixPatchCommitAdapter,
    PosixPatchJournalAndPreparationAdapter,
    PosixPatchWorkspaceSnapshotAdapter,
)
from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchJournalRecord,
    PatchJournalState,
    PatchMutationGuarantee,
    PatchPathOutcomeState,
    PatchRecoveryAction,
    PatchRecoveryStatus,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.use_cases import PlanPatch

DEFAULT_ADD_MODE = 0o644
EXECUTABLE_UPDATE_MODE = 0o755
OWNER_EXECUTABLE_MOVE_MODE = 0o700
STALE_STAGE_MODE = 0o600


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_stages_and_commits_add_update_delete_and_move(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "update.py").write_text("old update\n", encoding="utf-8")
    (tmp_path / "src" / "delete.py").write_text("delete me\n", encoding="utf-8")
    (tmp_path / "src" / "move.py").write_text("old move\n", encoding="utf-8")
    actions = (
        PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),
        PatchAction(index=1, kind=PatchActionKind.UPDATE, path="src/update.py", added_lines=("updated = True",)),
        PatchAction(index=2, kind=PatchActionKind.DELETE, path="src/delete.py"),
        PatchAction(
            index=3,
            kind=PatchActionKind.MOVE,
            path="src/move.py",
            destination_path="generated/move.py",
            added_lines=("moved = True",),
        ),
    )
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)

    assert run(adapter.prepare(plan, journal)) is None
    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.COMMITTED
    assert (tmp_path / "generated" / "add.py").read_text(encoding="utf-8") == "added = True\n"
    assert (tmp_path / "src" / "update.py").read_text(encoding="utf-8") == "updated = True\n"
    assert not (tmp_path / "src" / "delete.py").exists()
    assert not (tmp_path / "src" / "move.py").exists()
    assert (tmp_path / "generated" / "move.py").read_text(encoding="utf-8") == "moved = True\n"
    assert [outcome.final_state for outcome in result.path_outcomes] == [
        PatchPathOutcomeState.COMMITTED,
        PatchPathOutcomeState.COMMITTED,
        PatchPathOutcomeState.COMMITTED,
        PatchPathOutcomeState.COMMITTED,
    ]


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_persists_committed_journal_with_path_outcomes(tmp_path: Path) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.COMMITTED
    committed_evidence = result.path_outcomes[0].evidence
    assert committed_evidence is not None
    payload = json.loads(_journal_path(tmp_path, journal).read_text(encoding="utf-8"))
    assert payload["state"] == PatchJournalState.COMMITTED.value
    assert payload["path_outcomes"] == [
        {
            "evidence": {
                "content_digest": committed_evidence.content_digest,
                "exists": True,
                "identity_digest": committed_evidence.identity_digest,
                "metadata": dict(committed_evidence.metadata),
                "path": "generated/add.py",
            },
            "final_state": PatchPathOutcomeState.COMMITTED.value,
            "path": "generated/add.py",
            "planned_operation": PatchActionKind.ADD.value,
        }
    ]


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_journal_digest_mismatch_before_staging(tmp_path: Path) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    mismatched_journal = PatchJournalRecord(
        journal_digest=journal.journal_digest,
        plan_digest="sha256:" + "9" * 64,
        state=journal.state,
        created_directories=journal.created_directories,
    )

    result = run(PosixPatchCommitAdapter(tmp_path).prepare(plan, mismatched_journal))

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert not _stage_payload_path(tmp_path, journal, action_index=0).exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_stale_plan_before_visible_file_commit(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "update.py").write_text("old update\n", encoding="utf-8")
    actions = (
        PatchAction(index=0, kind=PatchActionKind.UPDATE, path="src/update.py", added_lines=("updated = True",)),
    )
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    (tmp_path / "src" / "update.py").write_text("external change\n", encoding="utf-8")

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert (tmp_path / "src" / "update.py").read_text(encoding="utf-8") == "external change\n"


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_replaced_destination_parent_before_visible_file_commit(
    tmp_path: Path,
) -> None:
    destination_parent = tmp_path / "generated"
    destination_parent.mkdir()
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    destination_parent.rmdir()
    destination_parent.mkdir()

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert not (tmp_path / "generated" / "add.py").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_add_destination_created_before_visible_file_commit(tmp_path: Path) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    (tmp_path / "generated" / "add.py").write_text("external file\n", encoding="utf-8")

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert (tmp_path / "generated" / "add.py").read_text(encoding="utf-8") == "external file\n"


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_move_destination_created_before_visible_file_commit(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "move.py").write_text("old move\n", encoding="utf-8")
    actions = (
        PatchAction(
            index=0,
            kind=PatchActionKind.MOVE,
            path="src/move.py",
            destination_path="generated/move.py",
            added_lines=("moved = True",),
        ),
    )
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    (tmp_path / "generated" / "move.py").write_text("external destination\n", encoding="utf-8")

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert (tmp_path / "src" / "move.py").read_text(encoding="utf-8") == "old move\n"
    assert (tmp_path / "generated" / "move.py").read_text(encoding="utf-8") == "external destination\n"


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_missing_stage_payload_before_visible_file_commit(tmp_path: Path) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    stage_payload = _stage_payload_path(tmp_path, journal, action_index=0)
    stage_payload.unlink()

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert not (tmp_path / "generated" / "add.py").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_applies_modes_for_add_update_and_move(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    update_path = tmp_path / "src" / "update.sh"
    move_path = tmp_path / "src" / "move.sh"
    update_path.write_text("old update\n", encoding="utf-8")
    move_path.write_text("old move\n", encoding="utf-8")
    update_path.chmod(EXECUTABLE_UPDATE_MODE)
    move_path.chmod(OWNER_EXECUTABLE_MOVE_MODE)
    actions = (
        PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),
        PatchAction(index=1, kind=PatchActionKind.UPDATE, path="src/update.sh", added_lines=("updated",)),
        PatchAction(
            index=2,
            kind=PatchActionKind.MOVE,
            path="src/move.sh",
            destination_path="generated/move.sh",
            added_lines=("moved",),
        ),
    )
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)

    assert run(adapter.prepare(plan, journal)) is None
    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.COMMITTED
    assert S_IMODE((tmp_path / "generated" / "add.py").stat().st_mode) == DEFAULT_ADD_MODE
    assert S_IMODE(update_path.stat().st_mode) == EXECUTABLE_UPDATE_MODE
    assert S_IMODE((tmp_path / "generated" / "move.sh").stat().st_mode) == OWNER_EXECUTABLE_MOVE_MODE


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_changed_stage_payload_mode_before_visible_file_commit(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    update_path = tmp_path / "src" / "update.sh"
    update_path.write_text("old update\n", encoding="utf-8")
    update_path.chmod(EXECUTABLE_UPDATE_MODE)
    actions = (PatchAction(index=0, kind=PatchActionKind.UPDATE, path="src/update.sh", added_lines=("updated",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    stage_payload = _stage_payload_path(tmp_path, journal, action_index=0)
    stage_payload.chmod(STALE_STAGE_MODE)

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert update_path.read_text(encoding="utf-8") == "old update\n"
    assert S_IMODE(update_path.stat().st_mode) == EXECUTABLE_UPDATE_MODE


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rolls_back_created_directories_deepest_first(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="src/generated/nested/new.py"),)
    _plan, journal = _prepared_plan_and_journal(tmp_path, actions)

    result = run(PosixPatchCommitAdapter(tmp_path).roll_back(journal))

    assert result.status is PatchResultStatus.COMMIT_FAILED_ROLLED_BACK
    assert result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION
    assert not (tmp_path / "src" / "generated").exists()
    assert [outcome.final_state.value for outcome in result.directory_outcomes] == ["removed", "removed"]


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_roll_back_retains_directory_with_external_content(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="src/generated/new.py"),)
    _plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    (tmp_path / "src" / "generated" / "external.txt").write_text("external\n", encoding="utf-8")

    result = run(PosixPatchCommitAdapter(tmp_path).roll_back(journal))

    assert result.status is PatchResultStatus.RECOVERY_REQUIRED
    assert result.mutation_guarantee is PatchMutationGuarantee.REVERSIBLE_EFFECTS_RETAINED
    assert (tmp_path / "src" / "generated" / "external.txt").is_file()
    assert result.directory_outcomes[0].final_state.value == "retained_external_content"


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_startup_recovery_rolls_back_prepared_journal(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="src/generated/new.py"),)
    _plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)

    decision = run(adapter.inspect(journal))
    result = run(adapter.recover(journal))

    assert decision.action is PatchRecoveryAction.ROLL_BACK_PREPARATION
    assert decision.status is PatchRecoveryStatus.ROLLED_BACK
    assert result.status is PatchResultStatus.COMMIT_FAILED_ROLLED_BACK
    assert not (tmp_path / "src" / "generated").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_startup_recovery_requires_operator_for_commit_journal(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="src/generated/new.py"),)
    _plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    committing_journal = PatchJournalRecord(
        journal_digest=journal.journal_digest,
        plan_digest=journal.plan_digest,
        state=PatchJournalState.COMMITTING,
        created_directories=journal.created_directories,
    )
    adapter = PosixPatchCommitAdapter(tmp_path)

    decision = run(adapter.inspect(committing_journal))
    result = run(adapter.recover(committing_journal))

    assert decision.action is PatchRecoveryAction.REQUIRE_OPERATOR_RECOVERY
    assert decision.status is PatchRecoveryStatus.RECOVERY_REQUIRED
    assert result.status is PatchResultStatus.RECOVERY_REQUIRED
    assert result.error is not None
    assert result.error.code == "RECOVERY_REQUIRED"


def _prepared_plan_and_journal(tmp_path: Path, actions: tuple[PatchAction, ...]):
    snapshot = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot(actions)
    assert not hasattr(snapshot, "status")
    planned = PlanPatch().plan(actions, snapshot)
    assert planned.plan is not None
    journal_adapter = PosixPatchJournalAndPreparationAdapter(tmp_path)
    journal = run(journal_adapter.create(planned.plan))
    assert run(journal_adapter.prepare(planned.plan, journal)) is None
    prepared_journal = run(journal_adapter.list_incomplete())[0]
    assert prepared_journal.state is PatchJournalState.PREPARED
    return planned.plan, prepared_journal


def _stage_payload_path(tmp_path: Path, journal: PatchJournalRecord, *, action_index: int) -> Path:
    return (
        tmp_path
        / ".fabrica"
        / "apply-patch"
        / "stage"
        / journal.journal_digest.removeprefix("sha256:")
        / f"{action_index:06d}.payload"
    )


def _journal_path(tmp_path: Path, journal: PatchJournalRecord) -> Path:
    return tmp_path / ".fabrica" / "apply-patch" / "journal" / f"{journal.journal_digest}.json"
