"""Integration tests for POSIX apply-patch staging and commit."""

import sys
from asyncio import run
from pathlib import Path

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
    PatchPathOutcomeState,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.use_cases import PlanPatch


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
    prepared_journal = PatchJournalRecord(
        journal_digest=journal.journal_digest,
        plan_digest=journal.plan_digest,
        state=PatchJournalState.PREPARED,
        created_directories=planned.plan.created_directories,
    )
    return planned.plan, prepared_journal
