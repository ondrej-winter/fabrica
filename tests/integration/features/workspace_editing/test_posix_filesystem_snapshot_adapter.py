"""Integration tests for the POSIX apply-patch snapshot adapter."""

import os
import socket
import sys
from asyncio import run
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import PosixPatchWorkspaceSnapshotAdapter
from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchResult,
    PatchResultStatus,
)


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_collects_source_destination_and_directory_evidence(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "old.py").write_text("value = 1\n", encoding="utf-8")
    actions = (
        PatchAction(index=0, kind=PatchActionKind.UPDATE, path="src/old.py"),
        PatchAction(index=1, kind=PatchActionKind.ADD, path="generated/new.py", added_lines=("value = 2",)),
    )

    snapshot = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot(actions)

    assert not hasattr(snapshot, "status")
    assert snapshot.evidence_by_path["src/old.py"].exists is True
    assert snapshot.evidence_by_path["src/old.py"].content_digest == "sha256:" + sha256(b"value = 1\n").hexdigest()
    assert snapshot.evidence_by_path["generated/new.py"].exists is False
    assert "src" in snapshot.existing_directories
    assert "generated" not in snapshot.existing_directories


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_fails_closed_without_production_capability(tmp_path: Path) -> None:
    result = run(PosixPatchWorkspaceSnapshotAdapter(tmp_path).verify_workspace_capabilities())

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "UNSUPPORTED_FILESYSTEM_GUARANTEE"


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
@pytest.mark.parametrize(
    ("setup", "action", "expected_code"),
    [
        (
            lambda root: (root / "link.py").symlink_to(root / "target.py"),
            PatchAction(index=0, kind=PatchActionKind.UPDATE, path="link.py"),
            "SYMLINK_PATH_UNSUPPORTED",
        ),
        (
            lambda root: (root / "existing.py").write_text("x\n", encoding="utf-8"),
            PatchAction(index=0, kind=PatchActionKind.ADD, path="existing.py", added_lines=("new",)),
            "ADD_TARGET_EXISTS",
        ),
        (
            lambda root: (root / "parent").write_text("not a directory", encoding="utf-8"),
            PatchAction(index=0, kind=PatchActionKind.ADD, path="parent/new.py", added_lines=("new",)),
            "PARENT_PATH_NOT_DIRECTORY",
        ),
    ],
)
def test_posix_snapshot_adapter_rejects_unsafe_paths_without_mutation(
    tmp_path: Path,
    setup,
    action: PatchAction,
    expected_code: str,
) -> None:
    setup(tmp_path)

    result = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot((action,))

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == expected_code


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_rejects_multiple_hard_links(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    alias = tmp_path / "alias.py"
    source.write_text("x\n", encoding="utf-8")
    os.link(source, alias)

    result = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot((PatchAction(index=0, kind=PatchActionKind.UPDATE, path="source.py"),))

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "MULTIPLE_HARD_LINKS_UNSUPPORTED"


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
@pytest.mark.parametrize(
    "action",
    [
        PatchAction(index=0, kind=PatchActionKind.UPDATE, path="special-node"),
        PatchAction(index=0, kind=PatchActionKind.ADD, path="special-node", added_lines=("new",)),
    ],
)
def test_posix_snapshot_adapter_rejects_fifo_file_paths_without_mutation(
    tmp_path: Path,
    action: PatchAction,
) -> None:
    fifo_path = tmp_path / "special-node"
    os.mkfifo(fifo_path)
    original_stat = fifo_path.lstat()

    result = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot((action,))

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "SPECIAL_FILE_UNSUPPORTED"
    current_stat = fifo_path.lstat()
    assert current_stat.st_dev == original_stat.st_dev
    assert current_stat.st_ino == original_stat.st_ino


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
@pytest.mark.parametrize(
    "action",
    [
        PatchAction(index=0, kind=PatchActionKind.UPDATE, path="socket-node"),
        PatchAction(index=0, kind=PatchActionKind.ADD, path="socket-node", added_lines=("new",)),
    ],
)
def test_posix_snapshot_adapter_rejects_unix_socket_paths_without_mutation(action: PatchAction) -> None:
    with TemporaryDirectory(prefix="fab-", dir="/tmp") as workspace:
        workspace_root = Path(workspace)
        socket_path = workspace_root / "socket-node"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_socket:
            unix_socket.bind(str(socket_path))
            original_stat = socket_path.lstat()

            result = PosixPatchWorkspaceSnapshotAdapter(
                workspace_root,
                require_production_capabilities=False,
            ).build_planning_snapshot((action,))

            assert isinstance(result, PatchResult)
            assert result.status is PatchResultStatus.REJECTED
            assert result.error is not None
            assert result.error.code == "SPECIAL_FILE_UNSUPPORTED"
            current_stat = socket_path.lstat()
            assert current_stat.st_dev == original_stat.st_dev
            assert current_stat.st_ino == original_stat.st_ino


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_rejects_unix_socket_parent_without_mutation() -> None:
    with TemporaryDirectory(prefix="fab-", dir="/tmp") as workspace:
        workspace_root = Path(workspace)
        socket_path = workspace_root / "socket-parent"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_socket:
            unix_socket.bind(str(socket_path))
            original_stat = socket_path.lstat()

            result = PosixPatchWorkspaceSnapshotAdapter(
                workspace_root,
                require_production_capabilities=False,
            ).build_planning_snapshot(
                (PatchAction(index=0, kind=PatchActionKind.ADD, path="socket-parent/new.py", added_lines=("new",)),)
            )

            assert isinstance(result, PatchResult)
            assert result.status is PatchResultStatus.REJECTED
            assert result.error is not None
            assert result.error.code == "SPECIAL_FILE_UNSUPPORTED"
            current_stat = socket_path.lstat()
            assert current_stat.st_dev == original_stat.st_dev
            assert current_stat.st_ino == original_stat.st_ino
            assert not (socket_path / "new.py").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_rejects_fifo_parent_without_mutation(tmp_path: Path) -> None:
    fifo_parent = tmp_path / "fifo-parent"
    os.mkfifo(fifo_parent)

    result = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot(
        (PatchAction(index=0, kind=PatchActionKind.ADD, path="fifo-parent/new.py", added_lines=("new",)),)
    )

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "SPECIAL_FILE_UNSUPPORTED"
    assert not (tmp_path / "fifo-parent" / "new.py").exists()
