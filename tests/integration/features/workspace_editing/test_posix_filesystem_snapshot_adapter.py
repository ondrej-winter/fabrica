"""Integration tests for the POSIX apply-patch snapshot adapter."""

import os
import socket
import sys
import unicodedata
from asyncio import run
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import PosixPatchWorkspaceSnapshotAdapter
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import adapter as posix_snapshot_adapter
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.adapter import (
    _list_extended_attribute_names,
    _list_extended_attributes,
    _reject_cross_device_move,
    _reject_path_alias,
    _reject_unsupported_metadata,
)
from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchMutationGuarantee,
    PatchPathEvidence,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error


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
def test_posix_snapshot_adapter_rejects_cross_device_move_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.py"
    source.write_text("original\n", encoding="utf-8")
    source_device = source.stat().st_dev
    monkeypatch.setattr(posix_snapshot_adapter, "_destination_parent_device", lambda _root, _path: source_device + 1)

    result = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot(
        (PatchAction(index=0, kind=PatchActionKind.MOVE, path="source.py", destination_path="generated/new.py"),)
    )

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "CROSS_DEVICE_MOVE_UNSUPPORTED"
    assert source.read_text(encoding="utf-8") == "original\n"
    assert not (tmp_path / "generated").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_accepts_same_device_move_with_missing_destination_parent(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("original\n", encoding="utf-8")

    snapshot = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot(
        (PatchAction(index=0, kind=PatchActionKind.MOVE, path="source.py", destination_path="generated/new.py"),)
    )

    assert not isinstance(snapshot, PatchResult)
    assert snapshot.evidence_by_path["source.py"].metadata["device"] == source.stat().st_dev
    assert snapshot.evidence_by_path["generated/new.py"].exists is False
    assert not (tmp_path / "generated").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_rejects_move_when_destination_device_cannot_be_inspected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = PatchAction(index=0, kind=PatchActionKind.MOVE, path="source.py", destination_path="generated/new.py")
    source_evidence = PatchPathEvidence(path="source.py", exists=True, metadata={"device": 1})
    monkeypatch.setattr(
        posix_snapshot_adapter,
        "_destination_parent_device",
        lambda _root, _path: (_ for _ in ()).throw(PermissionError("denied")),
    )

    result = _reject_cross_device_move(tmp_path, action, source_evidence)

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "IO_ERROR"


def test_posix_snapshot_adapter_reject_cross_device_move_requires_complete_move_evidence(tmp_path: Path) -> None:
    action = PatchAction(index=0, kind=PatchActionKind.MOVE, path="source.py", destination_path="generated/new.py")

    with pytest.raises(ValueError, match="source evidence"):
        _reject_cross_device_move(tmp_path, action, None)


def test_posix_snapshot_adapter_reject_cross_device_move_requires_integer_source_device(tmp_path: Path) -> None:
    action = PatchAction(index=0, kind=PatchActionKind.MOVE, path="source.py", destination_path="generated/new.py")
    source_evidence = PatchPathEvidence(path="source.py", exists=True, metadata={"device": "one"})

    with pytest.raises(TypeError, match="integer device"):
        _reject_cross_device_move(tmp_path, action, source_evidence)


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


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
@pytest.mark.parametrize(
    ("existing_name", "requested_name"),
    [("Module.py", "module.py"), ("Café.py", unicodedata.normalize("NFD", "Café.py"))],
)
def test_posix_snapshot_adapter_rejects_existing_path_aliases_without_mutation(
    tmp_path: Path,
    existing_name: str,
    requested_name: str,
) -> None:
    existing_path = tmp_path / existing_name
    existing_path.write_text("original\n", encoding="utf-8")
    actual_name = next(tmp_path.iterdir()).name
    if unicodedata.normalize("NFC", actual_name).casefold() != unicodedata.normalize("NFC", requested_name).casefold():
        pytest.skip("filesystem did not preserve an equivalent alias spelling")
    if actual_name == requested_name:
        requested_name = existing_name if actual_name != existing_name else unicodedata.normalize("NFD", existing_name)

    result = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot(
        (PatchAction(index=0, kind=PatchActionKind.ADD, path=requested_name, added_lines=("replacement",)),)
    )

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "PATH_ALIAS_COLLISION"
    assert existing_path.read_text(encoding="utf-8") == "original\n"


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_rejects_parent_directory_alias_without_mutation(tmp_path: Path) -> None:
    (tmp_path / "Source").mkdir()

    result = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot(
        (PatchAction(index=0, kind=PatchActionKind.ADD, path="source/new.py", added_lines=("new",)),)
    )

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "PATH_ALIAS_COLLISION"
    assert not (tmp_path / "Source" / "new.py").exists()


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_fails_closed_when_alias_directory_scan_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_scandir(_path: Path) -> object:
        raise PermissionError

    monkeypatch.setattr(os, "scandir", fail_scandir)

    result = _reject_path_alias(tmp_path, "new.py")

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "IO_ERROR"


def test_posix_snapshot_adapter_allows_files_without_posix_flags() -> None:
    assert _reject_unsupported_metadata("src/example.py", flags=0) is None


def test_posix_snapshot_adapter_rejects_nonzero_posix_file_flags_before_mutation() -> None:
    result = _reject_unsupported_metadata("src/example.py", flags=2)

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "UNSUPPORTED_METADATA"


def test_posix_snapshot_adapter_allows_empty_extended_attribute_metadata() -> None:
    assert _reject_unsupported_metadata("src/example.py", flags=0, extended_attribute_names=()) is None


def test_posix_snapshot_adapter_allows_non_security_extended_attributes() -> None:
    assert (
        _reject_unsupported_metadata(
            "src/example.py",
            flags=0,
            extended_attribute_names=("com.apple.provenance",),
        )
        is None
    )


def test_posix_snapshot_adapter_rejects_acl_extended_attributes_before_mutation() -> None:
    result = _reject_unsupported_metadata(
        "src/example.py",
        flags=0,
        extended_attribute_names=("system.posix_acl_access",),
    )

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "UNSUPPORTED_METADATA"


def test_posix_snapshot_adapter_preserves_extended_attribute_inspection_rejection() -> None:
    inspection_error = patch_error("UNSUPPORTED_METADATA", message="xattr inspection failed")
    inspection_result = PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        error=inspection_error,
    )

    assert (
        _reject_unsupported_metadata(
            "src/example.py",
            flags=0,
            extended_attribute_names=inspection_result,
        )
        is inspection_result
    )


def test_posix_snapshot_adapter_rejects_uninspectable_extended_attributes_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unsupported_listxattr(_path: Path) -> tuple[str, ...]:
        raise NotImplementedError

    monkeypatch.setattr(posix_snapshot_adapter, "_list_extended_attributes", unsupported_listxattr)

    result = _list_extended_attribute_names(tmp_path / "example.py")

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "UNSUPPORTED_METADATA"


def test_posix_snapshot_adapter_uses_native_extended_attribute_listing_when_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def native_listxattr(path: Path, *, follow_symlinks: bool) -> tuple[str, ...]:
        assert path == tmp_path / "example.py"
        assert follow_symlinks is False
        return ("user.example",)

    monkeypatch.setattr(os, "listxattr", native_listxattr, raising=False)

    assert _list_extended_attributes(tmp_path / "example.py") == ("user.example",)


def test_posix_snapshot_adapter_fails_closed_without_extended_attribute_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(os, "listxattr", raising=False)
    monkeypatch.setattr(posix_snapshot_adapter.sys, "platform", "freebsd")

    with pytest.raises(NotImplementedError, match="inspection is unavailable"):
        _list_extended_attributes(tmp_path / "example.py")


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_rejects_unsupported_metadata_on_destination_parent_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "generated").mkdir()

    def reject_parent_metadata(
        path: str,
        *,
        flags: int,
        extended_attribute_names: tuple[str, ...] | PatchResult = (),
    ) -> PatchResult | None:
        del flags, extended_attribute_names
        if path == "generated":
            error = patch_error("UNSUPPORTED_METADATA", message="unsupported parent metadata")
            return PatchResult(
                status=PatchResultStatus.REJECTED,
                mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
                error=error,
            )
        return None

    monkeypatch.setattr(posix_snapshot_adapter, "_reject_unsupported_metadata", reject_parent_metadata)

    result = PosixPatchWorkspaceSnapshotAdapter(
        tmp_path,
        require_production_capabilities=False,
    ).build_planning_snapshot(
        (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/new.py", added_lines=("new",)),)
    )

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "UNSUPPORTED_METADATA"
    assert not (tmp_path / "generated" / "new.py").exists()
