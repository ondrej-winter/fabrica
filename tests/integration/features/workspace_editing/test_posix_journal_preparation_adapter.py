"""Integration tests for POSIX apply-patch journaled preparation effects."""

import json
import sys
from asyncio import run
from pathlib import Path

import pytest

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import PosixPatchJournalAndPreparationAdapter
from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchDirectoryOutcome,
    PatchDirectoryOutcomeState,
    PatchDirectoryPlannedEffect,
    PatchJournalRecord,
    PatchJournalState,
    PatchPathEvidence,
    PatchPathOutcome,
    PatchPathOutcomeState,
    PatchPlan,
    PatchResultStatus,
    PatchRollbackEntry,
)

PLAN_DIGEST = "sha256:" + "1" * 64


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX preparation adapter targets macOS/Linux")
def test_posix_journal_prepare_records_intent_before_creating_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    plan = _plan("src/generated", "src/generated/nested")
    adapter = PosixPatchJournalAndPreparationAdapter(tmp_path)

    journal = run(adapter.create(plan))
    journal_path = next((tmp_path / ".fabrica" / "apply-patch" / "journal").glob("*.json"))

    assert json.loads(journal_path.read_text(encoding="utf-8"))["state"] == PatchJournalState.PLANNED.value
    assert not (tmp_path / "src" / "generated").exists()

    result = run(adapter.prepare(plan, journal))

    assert result is None
    assert (tmp_path / "src" / "generated").is_dir()
    assert (tmp_path / "src" / "generated" / "nested").is_dir()
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    assert payload["state"] == PatchJournalState.PREPARED.value
    assert [item["final_state"] for item in payload["created_directories"]] == [
        PatchDirectoryOutcomeState.CREATED.value,
        PatchDirectoryOutcomeState.CREATED.value,
    ]


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX preparation adapter targets macOS/Linux")
def test_posix_journal_prepare_rolls_back_created_directories_after_failure(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    plan = _plan("src/generated", "src/generated/nested")
    adapter = PosixPatchJournalAndPreparationAdapter(tmp_path)
    journal = run(adapter.create(plan))
    (tmp_path / "src" / "generated").mkdir()

    result = run(adapter.prepare(plan, journal))

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "DIRECTORY_CREATION_UNSAFE"
    assert (tmp_path / "src" / "generated").is_dir()
    payload = json.loads(next((tmp_path / ".fabrica" / "apply-patch" / "journal").glob("*.json")).read_text())
    assert payload["state"] == PatchJournalState.ROLLED_BACK.value


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX preparation adapter targets macOS/Linux")
def test_posix_journal_lists_incomplete_records(tmp_path: Path) -> None:
    plan = _plan("generated")
    adapter = PosixPatchJournalAndPreparationAdapter(tmp_path)
    journal = run(adapter.create(plan))
    run(adapter.transition(journal, PatchJournalState.PREPARING))

    incomplete = run(adapter.list_incomplete())

    assert len(incomplete) == 1
    assert incomplete[0].state is PatchJournalState.PREPARING


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX preparation adapter targets macOS/Linux")
def test_posix_journal_rejects_illegal_transition(tmp_path: Path) -> None:
    adapter = PosixPatchJournalAndPreparationAdapter(tmp_path)
    journal = run(adapter.create(_plan("generated")))

    with pytest.raises(ValueError, match="illegal patch journal transition"):
        run(adapter.transition(journal, PatchJournalState.COMMITTED))


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX preparation adapter targets macOS/Linux")
def test_posix_journal_prepare_rejects_preexisting_directory_without_mutation(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    plan = _plan("src/generated", "src/generated/nested")
    adapter = PosixPatchJournalAndPreparationAdapter(tmp_path)
    journal = run(adapter.create(plan))
    (tmp_path / "src" / "generated").mkdir()
    (tmp_path / "src" / "generated" / "external.txt").write_text("external\n", encoding="utf-8")

    result = run(adapter.prepare(plan, journal))

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "DIRECTORY_CREATION_UNSAFE"
    assert (tmp_path / "src" / "generated" / "external.txt").is_file()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX preparation adapter targets macOS/Linux")
def test_posix_journal_list_incomplete_returns_empty_when_no_journal_root(tmp_path: Path) -> None:
    assert run(PosixPatchJournalAndPreparationAdapter(tmp_path).list_incomplete()) == ()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX preparation adapter targets macOS/Linux")
def test_posix_journal_round_trips_path_outcomes_and_rollback_entries(tmp_path: Path) -> None:
    adapter = PosixPatchJournalAndPreparationAdapter(tmp_path)
    journal = run(adapter.create(_plan("generated")))
    rollback_entry = PatchRollbackEntry(
        path="src/original.py",
        operation=PatchActionKind.UPDATE,
        destination_path=None,
        backup_path=".fabrica/apply-patch/stage/backup.preimage",
        preimage=PatchPathEvidence(path="src/original.py", exists=True, content_digest="sha256:" + "2" * 64),
        postimage=PatchPathEvidence(path="src/original.py", exists=True, content_digest="sha256:" + "3" * 64),
    )
    outcome = PatchPathOutcome(
        path="src/original.py",
        planned_operation=PatchActionKind.UPDATE,
        final_state=PatchPathOutcomeState.COMMITTED,
        evidence=rollback_entry.postimage,
    )
    absent_postimage_entry = PatchRollbackEntry(
        path="generated/new.py",
        operation=PatchActionKind.ADD,
        destination_path=None,
        backup_path=None,
        preimage=PatchPathEvidence(path="generated/new.py", exists=False),
    )
    no_evidence_outcome = PatchPathOutcome(
        path="generated/new.py",
        planned_operation=PatchActionKind.ADD,
        final_state=PatchPathOutcomeState.UNKNOWN,
    )
    populated_journal = PatchJournalRecord(
        journal_digest=journal.journal_digest,
        plan_digest=journal.plan_digest,
        state=journal.state,
        created_directories=journal.created_directories,
        path_outcomes=(outcome, no_evidence_outcome),
        rollback_entries=(rollback_entry, absent_postimage_entry),
    )
    run(adapter.transition(populated_journal, PatchJournalState.PREPARING))

    restored = run(adapter.list_incomplete())[0]

    assert restored.path_outcomes == (outcome, no_evidence_outcome)
    assert restored.rollback_entries == (rollback_entry, absent_postimage_entry)


def _plan(*directories: str) -> PatchPlan:
    return PatchPlan(
        plan_digest=PLAN_DIGEST,
        actions=(PatchAction(index=0, kind=PatchActionKind.ADD, path="src/generated/nested/new.py"),),
        created_directories=tuple(
            PatchDirectoryOutcome(
                path=path,
                planned_effect=PatchDirectoryPlannedEffect.CREATE_DIRECTORY,
                final_state=PatchDirectoryOutcomeState.NOT_CREATED,
                reason="parent_for_destination",
            )
            for path in directories
        ),
    )
