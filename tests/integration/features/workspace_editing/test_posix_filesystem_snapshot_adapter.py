"""Integration tests for the POSIX apply-patch snapshot adapter."""

import os
import socket
import stat
import sys
import unicodedata
from asyncio import run
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import (
    PosixPatchWorkspaceSnapshotAdapter,
    capabilities,
)
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import adapter as posix_snapshot_adapter
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.adapter import (
    _destination_parent_device,
    _list_extended_attribute_names,
    _list_extended_attributes,
    _reject_cross_device_move,
    _reject_path_alias,
    _reject_unsupported_metadata,
    _snapshot_action_destination,
    _snapshot_action_source,
    _snapshot_optional_path,
    _unsupported_existing_path_result,
    _validate_existing_parent,
    _validate_parent_chain,
)
from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchMutationGuarantee,
    PatchPathEvidence,
    PatchPlan,
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

    snapshot = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(actions)

    assert not hasattr(snapshot, "status")
    assert snapshot.evidence_by_path["src/old.py"].exists is True
    assert snapshot.evidence_by_path["src/old.py"].content_digest == "sha256:" + sha256(b"value = 1\n").hexdigest()
    assert snapshot.evidence_by_path["generated/new.py"].exists is False
    assert "src" in snapshot.existing_directories
    assert "generated" not in snapshot.existing_directories


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX snapshot adapter targets macOS/Linux")
def test_posix_snapshot_adapter_fails_closed_without_production_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capabilities, "supervised_helper_ownership_available", lambda: False)

    result = run(PosixPatchWorkspaceSnapshotAdapter(tmp_path).verify_workspace_capabilities())

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "UNSUPPORTED_FILESYSTEM_GUARANTEE"
    assert result.error.metadata["backend"]
    assert result.error.metadata["filesystem_type"]
    assert result.error.metadata["workspace_device"] == tmp_path.stat().st_dev
    assert "supervised_helper_ownership" in str(result.error.metadata["unsupported_reasons"])


def test_posix_snapshot_adapter_reads_supported_text_and_rejects_binary_or_missing_sources(tmp_path: Path) -> None:
    adapter = PosixPatchWorkspaceSnapshotAdapter(tmp_path)
    (tmp_path / "source.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "binary.py").write_bytes(b"\0")

    snapshot = run(adapter.read_text_snapshot("source.py"))
    binary_result = run(adapter.read_text_snapshot("binary.py"))
    missing_result = run(adapter.read_text_snapshot("missing.py"))

    assert not isinstance(snapshot, PatchResult)
    assert snapshot.lines == ("value = 1",)
    assert isinstance(binary_result, PatchResult)
    assert binary_result.error is not None
    assert binary_result.error.code == "BINARY_FILE"
    assert isinstance(missing_result, PatchResult)
    assert missing_result.error is not None
    assert missing_result.error.code == "IO_ERROR"


def test_posix_snapshot_adapter_rejects_missing_workspace_root_without_mutation(tmp_path: Path) -> None:
    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path / "missing").build_planning_snapshot(())

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "IO_ERROR"


def test_posix_snapshot_adapter_rejects_path_alias_inspection_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_scandir(_path: Path) -> object:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(posix_snapshot_adapter.os, "scandir", deny_scandir)

    result = _reject_path_alias(tmp_path, "new.py")

    assert result is not None
    assert result.error is not None
    assert result.error.code == "IO_ERROR"


def test_posix_snapshot_adapter_uses_existing_root_device_for_missing_destination_parents(tmp_path: Path) -> None:
    assert _destination_parent_device(tmp_path, "generated/nested/new.py") == tmp_path.stat().st_dev


def test_posix_snapshot_adapter_returns_none_for_accepted_capabilities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        posix_snapshot_adapter,
        "collect_posix_patch_workspace_capability_evidence",
        lambda _root: capabilities.PosixPatchWorkspaceCapabilityEvidence(
            platform="darwin",
            machine="arm64",
            workspace_device=1,
            filesystem_type="apfs",
            backend="native",
            probes=(
                capabilities.PosixPatchCapabilityProbe(
                    "all_required", capabilities.PosixPatchCapabilityStatus.SUPPORTED, "supported"
                ),
            ),
        ),
    )

    assert run(PosixPatchWorkspaceSnapshotAdapter(tmp_path).verify_workspace_capabilities()) is None


def test_posix_snapshot_adapter_returns_current_revalidation_rejection(tmp_path: Path) -> None:
    plan = PatchPlan(
        plan_digest="sha256:" + "a" * 64,
        actions=(PatchAction(index=0, kind=PatchActionKind.UPDATE, path="missing.py"),),
    )

    result = run(PosixPatchWorkspaceSnapshotAdapter(tmp_path).snapshot_plan_inputs(plan))

    assert result is not None
    assert result.error is not None
    assert result.error.code == "SOURCE_NOT_FOUND"


def test_posix_snapshot_adapter_returns_no_revalidation_result_for_current_plan(tmp_path: Path) -> None:
    plan = PatchPlan(plan_digest="sha256:" + "a" * 64)

    assert run(PosixPatchWorkspaceSnapshotAdapter(tmp_path).snapshot_plan_inputs(plan)) is None


def test_posix_snapshot_adapter_returns_planning_snapshot_for_current_actions(tmp_path: Path) -> None:
    snapshot = run(
        PosixPatchWorkspaceSnapshotAdapter(tmp_path).snapshot_for_planning(
            (PatchAction(index=0, kind=PatchActionKind.ADD, path="new.py", added_lines=("new",)),)
        )
    )

    assert not isinstance(snapshot, PatchResult)
    assert snapshot.evidence_by_path["new.py"].exists is False


def test_posix_snapshot_adapter_rejects_path_alias_lstat_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_lstat(_self: Path) -> os.stat_result:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(Path, "lstat", deny_lstat)

    result = _reject_path_alias(tmp_path, "new.py")

    assert result is not None
    assert result.error is not None
    assert result.error.code == "IO_ERROR"


def test_posix_snapshot_helpers_cover_missing_alias_entries_and_destination_alias_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_root = tmp_path / "missing"
    assert _reject_path_alias(missing_root, "new.py") is None

    alias_error = PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        error=patch_error("PATH_ALIAS_COLLISION", message="alias"),
    )
    action = PatchAction(index=0, kind=PatchActionKind.ADD, path="new.py", added_lines=("new",))
    monkeypatch.setattr(posix_snapshot_adapter, "_reject_path_alias", lambda _root, _path: alias_error)

    assert _snapshot_action_destination(tmp_path, action, None, {}) is alias_error


def test_posix_snapshot_helpers_reject_missing_root_device_symlink_parent_and_read_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(FileNotFoundError):
        _destination_parent_device(tmp_path / "missing", "generated/new.py")

    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / "link").symlink_to(external, target_is_directory=True)
    parent_result = _validate_parent_chain(tmp_path, "link/new.py")

    assert parent_result is not None
    assert parent_result.error is not None
    assert parent_result.error.code == "SYMLINK_PATH_UNSUPPORTED"

    target = tmp_path / "source.py"
    target.write_text("source", encoding="utf-8")

    def deny_read_bytes(_self: Path) -> bytes:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(Path, "read_bytes", deny_read_bytes)
    read_result = _snapshot_optional_path(tmp_path, "source.py")

    assert isinstance(read_result, PatchResult)
    assert read_result.error is not None
    assert read_result.error.code == "IO_ERROR"


def test_posix_snapshot_helpers_translate_source_destination_and_inspection_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    update = PatchAction(index=0, kind=PatchActionKind.UPDATE, path="missing.py")
    move = PatchAction(index=1, kind=PatchActionKind.MOVE, path="source.py", destination_path="existing.py")
    (tmp_path / "existing.py").write_text("existing", encoding="utf-8")

    source_result = _snapshot_action_source(tmp_path, update)
    destination_result = _snapshot_action_destination(
        tmp_path,
        move,
        PatchPathEvidence(path="source.py", exists=True),
        {},
    )

    assert isinstance(source_result, PatchResult)
    assert source_result.error is not None
    assert source_result.error.code == "SOURCE_NOT_FOUND"
    assert isinstance(destination_result, PatchResult)
    assert destination_result.error is not None
    assert destination_result.error.code == "MOVE_TARGET_EXISTS"

    def reject_optional_path(_root: Path, _path: str) -> PatchResult:
        return PatchResult(
            status=PatchResultStatus.REJECTED,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
            error=patch_error("IO_ERROR", message="inspection failed"),
        )

    monkeypatch.setattr(posix_snapshot_adapter, "_snapshot_optional_path", reject_optional_path)
    result = _snapshot_action_source(tmp_path, update)

    assert isinstance(result, PatchResult)
    assert result.error is not None
    assert result.error.code == "IO_ERROR"


def test_posix_snapshot_helpers_translate_parent_and_optional_path_os_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject_lstat(_self: Path) -> os.stat_result:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(Path, "lstat", reject_lstat)

    parent_result = _validate_parent_chain(tmp_path, "parent/new.py")
    optional_result = _snapshot_optional_path(tmp_path, "file.py")

    assert parent_result is not None
    assert parent_result.error is not None
    assert parent_result.error.code == "IO_ERROR"
    assert isinstance(optional_result, PatchResult)
    assert optional_result.error is not None
    assert optional_result.error.code == "IO_ERROR"


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

    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot((action,))

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

    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(
        (PatchAction(index=0, kind=PatchActionKind.UPDATE, path="source.py"),)
    )

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

    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(
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

    snapshot = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(
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


@pytest.mark.parametrize("file_type", [stat.S_IFCHR, stat.S_IFBLK])
def test_posix_snapshot_adapter_rejects_device_file_modes(file_type: int, tmp_path: Path) -> None:
    path_stat = os.stat_result((file_type | 0o600, 0, 0, 1, 0, 0, 0, 0, 0, 0))

    result = _unsupported_existing_path_result(tmp_path / "device-node", path_stat, "device-node")

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "SPECIAL_FILE_UNSUPPORTED"


@pytest.mark.parametrize("file_type", [stat.S_IFCHR, stat.S_IFBLK])
def test_posix_snapshot_adapter_rejects_device_parent_modes(file_type: int, tmp_path: Path) -> None:
    path_stat = os.stat_result((file_type | 0o600, 0, 0, 1, 0, 0, 0, 0, 0, 0))

    result = _validate_existing_parent(tmp_path / "device-parent", "device-parent", path_stat)

    assert result is not None
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "SPECIAL_FILE_UNSUPPORTED"


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

    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot((action,))

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

            result = PosixPatchWorkspaceSnapshotAdapter(workspace_root).build_planning_snapshot((action,))

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

            result = PosixPatchWorkspaceSnapshotAdapter(workspace_root).build_planning_snapshot(
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

    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(
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

    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(
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

    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(
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

    result = PosixPatchWorkspaceSnapshotAdapter(tmp_path).build_planning_snapshot(
        (PatchAction(index=0, kind=PatchActionKind.ADD, path="generated/new.py", added_lines=("new",)),)
    )

    assert isinstance(result, PatchResult)
    assert result.status is PatchResultStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "UNSUPPORTED_METADATA"
    assert not (tmp_path / "generated" / "new.py").exists()
