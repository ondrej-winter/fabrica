"""Tests for repository snapshot application DTOs."""

from dataclasses import FrozenInstanceError

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    GitRepositorySnapshot,
    GitRepositorySnapshotFailureCategory,
)

INDEX_TREE_ID = "a" * 40
TRACKED_WORKTREE_ID = "b" * 64


def test_repository_snapshot_preserves_valid_immutable_state_identifiers() -> None:
    snapshot = GitRepositorySnapshot(
        index_tree_id=INDEX_TREE_ID,
        tracked_worktree_id=TRACKED_WORKTREE_ID,
    )

    assert snapshot.index_tree_id == INDEX_TREE_ID
    assert snapshot.tracked_worktree_id == TRACKED_WORKTREE_ID
    with pytest.raises(FrozenInstanceError):
        snapshot.index_tree_id = "c" * 40  # ty: ignore[invalid-assignment]


def test_repository_snapshot_accepts_sha256_index_tree_identifier() -> None:
    snapshot = GitRepositorySnapshot(
        index_tree_id="a" * 64,
        tracked_worktree_id=TRACKED_WORKTREE_ID,
    )

    assert snapshot.index_tree_id == "a" * 64


@pytest.mark.parametrize(
    ("index_tree_id", "tracked_worktree_id"),
    [
        ("", TRACKED_WORKTREE_ID),
        ("A" * 40, TRACKED_WORKTREE_ID),
        ("g" * 40, TRACKED_WORKTREE_ID),
        ("a" * 39, TRACKED_WORKTREE_ID),
        ("a" * 41, TRACKED_WORKTREE_ID),
        (INDEX_TREE_ID, ""),
        (INDEX_TREE_ID, "B" * 64),
        (INDEX_TREE_ID, "g" * 64),
        (INDEX_TREE_ID, "b" * 63),
    ],
)
def test_repository_snapshot_rejects_malformed_state_identifiers(
    index_tree_id: str,
    tracked_worktree_id: str,
) -> None:
    with pytest.raises(ValueError, match="repository snapshot"):
        GitRepositorySnapshot(
            index_tree_id=index_tree_id,
            tracked_worktree_id=tracked_worktree_id,
        )


def test_repository_snapshot_failure_category_is_closed_set() -> None:
    assert GitRepositorySnapshotFailureCategory.MALFORMED_OUTPUT.value == "malformed_output"

    with pytest.raises(ValueError, match="is not a valid"):
        GitRepositorySnapshotFailureCategory("unexpected")
