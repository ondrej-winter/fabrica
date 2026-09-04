"""Integration tests for POSIX apply-patch staging and commit."""

import json
import os
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
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import commit as posix_commit_module
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
RESTRICTIVE_WORKSPACE_UMASK = 0o027
RESTRICTIVE_ADD_MODE = 0o640
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


@pytest.mark.skipif(
    sys.platform not in {"darwin", "linux"},
    reason="AP-02 native no-replace commit backend targets macOS/Linux",
)
def test_posix_commit_adapter_rejects_destination_created_at_native_commit_point_without_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("planned",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    destination = tmp_path / "generated" / "add.py"

    native_rename = posix_commit_module.rename_no_replace

    def create_racing_destination_before_native_rename(
        workspace_root: Path,
        source_path: str,
        destination_path: str,
    ) -> None:
        destination.write_text("external\n", encoding="utf-8")
        native_rename(workspace_root, source_path, destination_path)

    monkeypatch.setattr(posix_commit_module, "rename_no_replace", create_racing_destination_before_native_rename)

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.RECOVERY_REQUIRED
    assert destination.read_text(encoding="utf-8") == "external\n"


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
@pytest.mark.parametrize("failing_payload_number", [1, 2])
def test_posix_commit_adapter_cleans_staging_faults_before_visible_file_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failing_payload_number: int,
) -> None:
    (tmp_path / "src").mkdir()
    source_path = tmp_path / "src" / "existing.py"
    source_path.write_text("original\n", encoding="utf-8")
    actions = (
        PatchAction(index=0, kind=PatchActionKind.UPDATE, path="src/existing.py", added_lines=("updated",)),
        PatchAction(index=1, kind=PatchActionKind.ADD, path="generated/new.py", added_lines=("new",)),
    )
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    fsync_calls = 0

    def fail_during_staged_payload_fsync(path: Path) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == failing_payload_number:
            message = "injected staging durability failure"
            raise OSError(message)
        with path.open("rb") as handle:
            os.fsync(handle.fileno())

    monkeypatch.setattr(posix_commit_module, "_fsync_file", fail_during_staged_payload_fsync)

    result = run(PosixPatchCommitAdapter(tmp_path).prepare(plan, journal))

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "IO_ERROR"
    assert source_path.read_text(encoding="utf-8") == "original\n"
    assert not (tmp_path / "generated" / "new.py").exists()
    assert not _stage_payload_path(tmp_path, journal, action_index=0).parent.exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_commit_when_durable_journal_is_not_prepared(tmp_path: Path) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    journal_path = _journal_path(tmp_path, journal)
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    payload["state"] = PatchJournalState.COMMITTING.value
    journal_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert not (tmp_path / "generated" / "add.py").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_staging_when_durable_journal_plan_binding_changes(tmp_path: Path) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    journal_path = _journal_path(tmp_path, journal)
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    payload["plan_digest"] = "sha256:" + "0" * 64
    journal_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    result = run(PosixPatchCommitAdapter(tmp_path).prepare(plan, journal))

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert not _stage_payload_path(tmp_path, journal, action_index=0).exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_removes_partial_stage_artifacts_after_staging_io_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)

    def fail_staged_payload_sync(_path: Path) -> None:
        msg = "injected stage payload sync failure"
        raise OSError(msg)

    monkeypatch.setattr(posix_commit_module, "_fsync_file", fail_staged_payload_sync)

    result = run(PosixPatchCommitAdapter(tmp_path).prepare(plan, journal))

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "IO_ERROR"
    assert not _stage_payload_path(tmp_path, journal, action_index=0).exists()
    assert not _stage_payload_path(tmp_path, journal, action_index=0).parent.exists()


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
def test_posix_commit_adapter_rejects_same_length_changed_stage_payload_before_visible_file_commit(
    tmp_path: Path,
) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("approved",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)
    assert run(adapter.prepare(plan, journal)) is None
    _stage_payload_path(tmp_path, journal, action_index=0).write_bytes(b"tampered\n")

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
def test_posix_commit_adapter_applies_configured_workspace_umask_to_add_mode(tmp_path: Path) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path, workspace_umask=RESTRICTIVE_WORKSPACE_UMASK)

    assert run(adapter.prepare(plan, journal)) is None
    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.COMMITTED
    assert S_IMODE((tmp_path / "generated" / "add.py").stat().st_mode) == RESTRICTIVE_ADD_MODE


def test_posix_commit_adapter_rejects_invalid_workspace_umask(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="workspace_umask"):
        PosixPatchCommitAdapter(tmp_path, workspace_umask=0o1000)


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rejects_add_payload_with_mode_outside_configured_workspace_umask(tmp_path: Path) -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added = True",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path, workspace_umask=RESTRICTIVE_WORKSPACE_UMASK)
    assert run(adapter.prepare(plan, journal)) is None
    _stage_payload_path(tmp_path, journal, action_index=0).chmod(DEFAULT_ADD_MODE)

    result = run(adapter.commit(plan, journal))

    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "STALE_PLAN"
    assert not (tmp_path / "generated" / "add.py").exists()


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
    assert run(PosixPatchJournalAndPreparationAdapter(tmp_path).list_incomplete()) == ()


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


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rolls_back_committed_file_effects_from_durable_preimages(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    update_path = tmp_path / "src" / "update.py"
    delete_path = tmp_path / "src" / "delete.py"
    update_path.write_text("old update\n", encoding="utf-8")
    delete_path.write_text("delete me\n", encoding="utf-8")
    actions = (
        PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added",)),
        PatchAction(index=1, kind=PatchActionKind.UPDATE, path="src/update.py", added_lines=("updated",)),
        PatchAction(index=2, kind=PatchActionKind.DELETE, path="src/delete.py"),
    )
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)

    assert run(adapter.prepare(plan, journal)) is None
    assert run(adapter.commit(plan, journal)).status is PatchResultStatus.COMMITTED
    committed_journal = run(PosixPatchJournalAndPreparationAdapter(tmp_path).list_incomplete())
    assert committed_journal == ()
    journal_payload = json.loads(_journal_path(tmp_path, journal).read_text(encoding="utf-8"))
    assert journal_payload["rollback_entries"]

    # Reload the durable committing record to exercise the real restart path.
    _journal_path(tmp_path, journal).write_text(
        json.dumps({**journal_payload, "state": PatchJournalState.COMMITTING.value}), encoding="utf-8"
    )
    recovered_journal = run(PosixPatchJournalAndPreparationAdapter(tmp_path).list_incomplete())[0]
    result = run(adapter.recover(recovered_journal))

    assert result.status is PatchResultStatus.COMMIT_FAILED_ROLLED_BACK
    assert (tmp_path / "src" / "update.py").read_text(encoding="utf-8") == "old update\n"
    assert (tmp_path / "src" / "delete.py").read_text(encoding="utf-8") == "delete me\n"
    assert not (tmp_path / "generated" / "add.py").exists()
    assert [outcome.final_state is PatchPathOutcomeState.ROLLED_BACK for outcome in result.path_outcomes] == [
        True,
        True,
        True,
    ]


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_file_rollback_retains_independently_changed_path(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    update_path = tmp_path / "src" / "update.py"
    update_path.write_text("old update\n", encoding="utf-8")
    actions = (PatchAction(index=0, kind=PatchActionKind.UPDATE, path="src/update.py", added_lines=("updated",)),)
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)

    assert run(adapter.prepare(plan, journal)) is None
    assert run(adapter.commit(plan, journal)).status is PatchResultStatus.COMMITTED
    update_path.write_text("external\n", encoding="utf-8")
    journal_payload = json.loads(_journal_path(tmp_path, journal).read_text(encoding="utf-8"))
    _journal_path(tmp_path, journal).write_text(
        json.dumps({**journal_payload, "state": PatchJournalState.COMMITTING.value}), encoding="utf-8"
    )

    recovered_journal = run(PosixPatchJournalAndPreparationAdapter(tmp_path).list_incomplete())[0]
    result = run(adapter.recover(recovered_journal))

    assert result.status is PatchResultStatus.RECOVERY_REQUIRED
    assert update_path.read_text(encoding="utf-8") == "external\n"
    assert result.path_outcomes[0].final_state is PatchPathOutcomeState.UNKNOWN


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
def test_posix_commit_adapter_rolls_back_move_with_durable_preimage(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    source_path = tmp_path / "src" / "move.py"
    source_path.write_text("original\n", encoding="utf-8")
    actions = (
        PatchAction(
            index=0,
            kind=PatchActionKind.MOVE,
            path="src/move.py",
            destination_path="generated/move.py",
            added_lines=("moved",),
        ),
    )
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)
    adapter = PosixPatchCommitAdapter(tmp_path)

    assert run(adapter.prepare(plan, journal)) is None
    assert run(adapter.commit(plan, journal)).status is PatchResultStatus.COMMITTED
    journal_payload = json.loads(_journal_path(tmp_path, journal).read_text(encoding="utf-8"))
    _journal_path(tmp_path, journal).write_text(
        json.dumps({**journal_payload, "state": PatchJournalState.COMMITTING.value}), encoding="utf-8"
    )

    recovered_journal = run(PosixPatchJournalAndPreparationAdapter(tmp_path).list_incomplete())[0]
    result = run(adapter.recover(recovered_journal))

    assert result.status is PatchResultStatus.COMMIT_FAILED_ROLLED_BACK
    assert source_path.read_text(encoding="utf-8") == "original\n"
    assert not (tmp_path / "generated" / "move.py").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX commit adapter targets macOS/Linux")
@pytest.mark.parametrize("interrupted_action_index", [0, 1, 2, 3])
def test_posix_commit_adapter_recovers_after_interruption_at_each_visible_commit_step(
    tmp_path: Path, interrupted_action_index: int
) -> None:
    (tmp_path / "src").mkdir()
    update_path = tmp_path / "src" / "update.py"
    delete_path = tmp_path / "src" / "delete.py"
    move_path = tmp_path / "src" / "move.py"
    update_path.write_text("old update\n", encoding="utf-8")
    delete_path.write_text("delete me\n", encoding="utf-8")
    move_path.write_text("old move\n", encoding="utf-8")
    actions = (
        PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/add.py", added_lines=("added",)),
        PatchAction(index=1, kind=PatchActionKind.UPDATE, path="src/update.py", added_lines=("updated",)),
        PatchAction(index=2, kind=PatchActionKind.DELETE, path="src/delete.py"),
        PatchAction(
            index=3,
            kind=PatchActionKind.MOVE,
            path="src/move.py",
            destination_path="generated/move.py",
            added_lines=("moved",),
        ),
    )
    plan, journal = _prepared_plan_and_journal(tmp_path, actions)

    def interrupt_after_selected_action(action: PatchAction) -> None:
        if action.index == interrupted_action_index:
            raise _InjectedCommitInterruptionError

    interrupted_adapter = PosixPatchCommitAdapter(tmp_path, after_commit_step=interrupt_after_selected_action)
    assert run(interrupted_adapter.prepare(plan, journal)) is None

    with pytest.raises(_InjectedCommitInterruptionError):
        run(interrupted_adapter.commit(plan, journal))

    recovered_journal = run(PosixPatchJournalAndPreparationAdapter(tmp_path).list_incomplete())[0]
    result = run(PosixPatchCommitAdapter(tmp_path).recover(recovered_journal))

    assert recovered_journal.state is PatchJournalState.COMMITTING
    assert result.status is PatchResultStatus.COMMIT_FAILED_ROLLED_BACK
    assert not (tmp_path / "generated" / "add.py").exists()
    assert update_path.read_text(encoding="utf-8") == "old update\n"
    assert delete_path.read_text(encoding="utf-8") == "delete me\n"
    assert move_path.read_text(encoding="utf-8") == "old move\n"
    assert not (tmp_path / "generated" / "move.py").exists()


class _InjectedCommitInterruptionError(Exception):
    """Synthetic process interruption after a durable visible commit step."""


def _prepared_plan_and_journal(tmp_path: Path, actions: tuple[PatchAction, ...]):
    snapshot = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(actions)
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
    return tmp_path / ".fabrica" / "apply-patch" / "journal" / f"{journal.journal_digest.removeprefix('sha256:')}.json"
