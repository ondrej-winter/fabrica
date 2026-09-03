"""Tests for repository snapshot application ports."""

from fabrica.features.developer_workflow.application.dtos import (
    GitRepositorySnapshot,
    GitRepositorySnapshotFailureCategory,
)
from fabrica.features.developer_workflow.application.ports import (
    GitRepositorySnapshotLoadError,
    GitRepositorySnapshotReader,
)


def test_repository_snapshot_load_error_copies_safe_metadata() -> None:
    metadata = {"category": "malformed_output"}
    error = GitRepositorySnapshotLoadError(
        "repository snapshot output was malformed",
        category=GitRepositorySnapshotFailureCategory.MALFORMED_OUTPUT,
        metadata=metadata,
    )
    metadata["category"] = "changed"

    assert error.category is GitRepositorySnapshotFailureCategory.MALFORMED_OUTPUT
    assert error.metadata == {"category": "malformed_output"}


def test_repository_snapshot_reader_uses_application_boundary_types() -> None:
    assert GitRepositorySnapshotReader.load_snapshot.__annotations__ == {
        "return": GitRepositorySnapshot,
    }
    assert GitRepositorySnapshotReader.load_index_tree_id.__annotations__ == {
        "return": str,
    }


def test_repository_snapshot_contracts_are_exported_from_application_packages() -> None:
    assert GitRepositorySnapshot.__name__ == "GitRepositorySnapshot"
    assert GitRepositorySnapshotReader.__name__ == "GitRepositorySnapshotReader"
