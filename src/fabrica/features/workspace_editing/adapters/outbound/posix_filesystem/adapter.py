"""POSIX snapshot and capability adapter for apply-patch planning."""

import ctypes
import os
import stat
import sys
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.capabilities import (
    collect_posix_patch_workspace_capability_evidence,
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
from fabrica.features.workspace_editing.application.text_snapshot import (
    PatchTextDecodingError,
    PatchTextSnapshot,
    decode_patch_text,
)
from fabrica.features.workspace_editing.application.use_cases import PatchPlanningSnapshot

_SECURITY_RELEVANT_EXTENDED_ATTRIBUTE_PREFIXES = ("security.",)
_SECURITY_RELEVANT_EXTENDED_ATTRIBUTE_NAMES = frozenset(
    {
        "com.apple.macl",
        "system.posix_acl_access",
        "system.posix_acl_default",
    }
)


@dataclass(frozen=True, slots=True)
class PosixPatchWorkspaceSnapshotAdapter:
    """Build side-effect-free path evidence using POSIX filesystem facts."""

    workspace_root: Path

    async def verify_workspace_capabilities(self) -> PatchResult | None:
        """Return a fail-closed rejection unless actual workspace evidence is complete."""
        evidence = collect_posix_patch_workspace_capability_evidence(self.workspace_root)
        if evidence.production_ready:
            return None
        return _rejected(
            "UNSUPPORTED_FILESYSTEM_GUARANTEE",
            "workspace filesystem mutation guarantees are not available",
            metadata={
                "backend": evidence.backend,
                "filesystem_type": evidence.filesystem_type,
                "platform": evidence.platform,
                "unsupported_reasons": ",".join(evidence.unsupported_reasons),
                "workspace_device": evidence.workspace_device,
            },
        )

    async def snapshot_plan_inputs(self, plan: PatchPlan) -> PatchResult | None:
        """Revalidate a planned patch against current side-effect-free path facts."""
        snapshot_result = self.build_planning_snapshot(plan.actions)
        if isinstance(snapshot_result, PatchResult):
            return snapshot_result
        return None

    async def snapshot_for_planning(self, actions: tuple[PatchAction, ...]) -> PatchPlanningSnapshot | PatchResult:
        """Return planning evidence for parsed actions or a no-mutation rejection."""
        return self.build_planning_snapshot(actions)

    async def read_text_snapshot(self, path: str) -> PatchTextSnapshot | PatchResult:
        """Read and decode an existing workspace-relative text file."""
        try:
            return decode_patch_text((self._workspace_root() / path).read_bytes())
        except PatchTextDecodingError as err:
            return PatchResult(
                status=PatchResultStatus.REJECTED,
                mutation_guarantee=err.error.mutation_guarantee,
                error=err.error,
            )
        except OSError as err:
            return _rejected("IO_ERROR", f"could not read source text: {err.strerror}")

    def build_planning_snapshot(self, actions: tuple[PatchAction, ...]) -> PatchPlanningSnapshot | PatchResult:
        """Return planning evidence for parsed actions or a no-mutation rejection."""
        try:
            root = self._workspace_root()
        except OSError as err:
            return _rejected("IO_ERROR", f"could not resolve workspace root: {err.strerror}")

        evidence_by_path: dict[str, PatchPathEvidence] = {}
        existing_directories = {""}
        for directory in _walk_existing_directories(root):
            existing_directories.add(directory)

        for action in actions:
            action_result = _snapshot_action(root, action, evidence_by_path)
            if action_result is not None:
                return action_result

        return PatchPlanningSnapshot(
            evidence_by_path=evidence_by_path,
            existing_directories=frozenset(existing_directories),
        )

    def _workspace_root(self) -> Path:
        return self.workspace_root.resolve(strict=True)


def _walk_existing_directories(root: Path) -> tuple[str, ...]:
    directories: list[str] = []
    for current_root, dir_names, _file_names in os.walk(root, followlinks=False):
        current_path = Path(current_root)
        relative = current_path.relative_to(root).as_posix()
        if relative != ".":
            directories.append(relative)
        dir_names[:] = [name for name in dir_names if not (current_path / name).is_symlink()]
    return tuple(directories)


def _reject_path_alias(root: Path, path: str) -> PatchResult | None:
    current = root
    result: PatchResult | None = None
    for part in path.split("/"):
        try:
            current_stat = current.lstat()
        except OSError as err:
            if not isinstance(err, FileNotFoundError):
                result = _rejected("IO_ERROR", f"could not inspect path aliases: {err.strerror}")
            break
        if not stat.S_ISDIR(current_stat.st_mode):
            break

        try:
            entry_names = tuple(entry.name for entry in os.scandir(current))
        except OSError as err:
            if not isinstance(err, FileNotFoundError):
                result = _rejected("IO_ERROR", f"could not inspect path aliases: {err.strerror}")
            break

        normalized_part = unicodedata.normalize("NFC", part).casefold()
        aliases = [
            name
            for name in entry_names
            if name != part and unicodedata.normalize("NFC", name).casefold() == normalized_part
        ]
        if aliases:
            result = _rejected("PATH_ALIAS_COLLISION", f"path spelling aliases an existing entry: {path}")
            break
        if part not in entry_names:
            return None
        current /= part
    return result


def _snapshot_action(
    root: Path,
    action: PatchAction,
    evidence_by_path: dict[str, PatchPathEvidence],
) -> PatchResult | None:
    alias_result = _reject_path_alias(root, action.path)
    if alias_result is not None:
        return alias_result

    source_result = _snapshot_action_source(root, action)
    if isinstance(source_result, PatchResult):
        return source_result
    if source_result is not None:
        evidence_by_path[action.path] = source_result
    return _snapshot_action_destination(root, action, source_result, evidence_by_path)


def _snapshot_action_destination(
    root: Path,
    action: PatchAction,
    source_evidence: PatchPathEvidence | None,
    evidence_by_path: dict[str, PatchPathEvidence],
) -> PatchResult | None:
    destination = action.path if action.kind is PatchActionKind.ADD else action.destination_path
    if destination is None:
        return None
    alias_result = _reject_path_alias(root, destination)
    if alias_result is not None:
        return alias_result
    destination_result = _snapshot_destination(root, action.kind, destination)
    if isinstance(destination_result, PatchResult):
        return destination_result
    if action.kind is PatchActionKind.MOVE:
        cross_device_result = _reject_cross_device_move(root, action, source_evidence)
        if cross_device_result is not None:
            return cross_device_result
    evidence_by_path[destination] = destination_result
    return None


def _snapshot_action_source(root: Path, action: PatchAction) -> PatchPathEvidence | PatchResult | None:
    if action.kind is PatchActionKind.ADD:
        return None
    evidence = _snapshot_existing_file(root, action.path)
    if isinstance(evidence, PatchResult):
        return evidence
    if not evidence.exists:
        return _rejected("SOURCE_NOT_FOUND", f"source path does not exist: {action.path}")
    return evidence


def _snapshot_destination(root: Path, action_kind: PatchActionKind, path: str) -> PatchPathEvidence | PatchResult:
    parent_result = _validate_parent_chain(root, path)
    if parent_result is not None:
        return parent_result
    evidence = _snapshot_optional_path(root, path)
    if isinstance(evidence, PatchResult):
        return evidence
    if action_kind is PatchActionKind.ADD and evidence.exists:
        return _rejected("ADD_TARGET_EXISTS", f"add target already exists: {path}")
    if action_kind is PatchActionKind.MOVE and evidence.exists:
        return _rejected("MOVE_TARGET_EXISTS", f"move target already exists: {path}")
    return evidence


def _reject_cross_device_move(
    root: Path,
    action: PatchAction,
    source_evidence: PatchPathEvidence | None,
) -> PatchResult | None:
    if source_evidence is None or action.destination_path is None:
        msg = "move actions must have source evidence and a destination path"
        raise ValueError(msg)
    source_device = source_evidence.metadata.get("device")
    if not isinstance(source_device, int):
        msg = "move source evidence must include an integer device"
        raise TypeError(msg)
    try:
        destination_device = _destination_parent_device(root, action.destination_path)
    except OSError as err:
        return _rejected("IO_ERROR", f"could not inspect move destination device: {err.strerror}")
    if source_device != destination_device:
        return _rejected(
            "CROSS_DEVICE_MOVE_UNSUPPORTED",
            f"move source and destination parent are on different devices: {action.path} -> {action.destination_path}",
        )
    return None


def _destination_parent_device(root: Path, destination_path: str) -> int:
    parent = root / destination_path.rpartition("/")[0]
    while True:
        try:
            return parent.stat().st_dev
        except FileNotFoundError:
            if parent == root:
                raise
            parent = parent.parent


def _validate_parent_chain(root: Path, path: str) -> PatchResult | None:
    parent = path.rpartition("/")[0]
    if not parent:
        return None
    current = root
    for part in parent.split("/"):
        current = current / part
        try:
            path_stat = current.lstat()
        except FileNotFoundError:
            return None
        except OSError as err:
            return _rejected("IO_ERROR", f"could not inspect parent path: {err.strerror}")
        parent_result = _validate_existing_parent(current, parent, path_stat)
        if parent_result is not None:
            return parent_result
    return None


def _validate_existing_parent(current: Path, parent: str, path_stat: os.stat_result) -> PatchResult | None:
    if stat.S_ISLNK(path_stat.st_mode):
        return _rejected("SYMLINK_PATH_UNSUPPORTED", f"symlink parent is unsupported: {parent}")
    if not stat.S_ISDIR(path_stat.st_mode):
        code = "PARENT_PATH_NOT_DIRECTORY" if stat.S_ISREG(path_stat.st_mode) else "SPECIAL_FILE_UNSUPPORTED"
        message = (
            "parent path is not a directory"
            if stat.S_ISREG(path_stat.st_mode)
            else "special-file parent is unsupported"
        )
        return _rejected(code, f"{message}: {parent}")
    return _reject_unsupported_metadata(
        parent,
        flags=getattr(path_stat, "st_flags", 0),
        extended_attribute_names=_list_extended_attribute_names(current),
    )


def _snapshot_existing_file(root: Path, path: str) -> PatchPathEvidence | PatchResult:
    evidence = _snapshot_optional_path(root, path)
    if isinstance(evidence, PatchResult) or not evidence.exists:
        return evidence
    return evidence


def _snapshot_optional_path(root: Path, path: str) -> PatchPathEvidence | PatchResult:
    absolute = root / path
    try:
        path_stat = absolute.lstat()
    except FileNotFoundError:
        return PatchPathEvidence(
            path=path,
            exists=False,
            metadata={"ancestor_identity_digest": _ancestor_digest(root, path)},
        )
    except OSError as err:
        return _rejected("IO_ERROR", f"could not inspect path: {err.strerror}")

    unsupported_result = _unsupported_existing_path_result(absolute, path_stat, path)
    if unsupported_result is not None:
        return unsupported_result

    try:
        content = absolute.read_bytes()
    except OSError as err:
        return _rejected("IO_ERROR", f"could not read path: {err.strerror}")
    return PatchPathEvidence(
        path=path,
        exists=True,
        content_digest=_digest_bytes(content),
        identity_digest=_identity_digest(path_stat),
        metadata={
            "ancestor_identity_digest": _ancestor_digest(root, path),
            "device": path_stat.st_dev,
            "inode": path_stat.st_ino,
            "mode": stat.S_IMODE(path_stat.st_mode),
            "size": path_stat.st_size,
        },
    )


def _ancestor_digest(root: Path, path: str) -> str:
    parent = path.rpartition("/")[0]
    current = root if not parent else root / parent
    try:
        path_stat = current.stat()
    except OSError:
        current = root
        path_stat = current.stat()
    return _directory_identity_digest(path_stat)


def _directory_identity_digest(path_stat: os.stat_result) -> str:
    payload = f"{path_stat.st_dev}:{path_stat.st_ino}:{path_stat.st_mode}"
    return _digest_bytes(payload.encode("utf-8"))


def _identity_digest(path_stat: os.stat_result) -> str:
    payload = f"{path_stat.st_dev}:{path_stat.st_ino}:{path_stat.st_mode}:{path_stat.st_nlink}"
    return _digest_bytes(payload.encode("utf-8"))


def _digest_bytes(content: bytes) -> str:
    return "sha256:" + sha256(content).hexdigest()


def _rejected(code: str, message: str, *, metadata: dict[str, str | int | None] | None = None) -> PatchResult:
    error = patch_error(code, message=message, metadata=metadata)
    return PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        error=error,
    )


__all__ = ["PosixPatchWorkspaceSnapshotAdapter"]


def _unsupported_existing_path_result(absolute: Path, path_stat: os.stat_result, path: str) -> PatchResult | None:
    if stat.S_ISLNK(path_stat.st_mode):
        return _rejected("SYMLINK_PATH_UNSUPPORTED", f"symlink paths are unsupported: {path}")
    if not stat.S_ISREG(path_stat.st_mode):
        code = "PARENT_PATH_NOT_DIRECTORY" if stat.S_ISDIR(path_stat.st_mode) else "SPECIAL_FILE_UNSUPPORTED"
        return _rejected(code, f"path is not a regular file: {path}")
    if path_stat.st_nlink != 1:
        return _rejected("MULTIPLE_HARD_LINKS_UNSUPPORTED", f"multiple hard links are unsupported: {path}")
    return _reject_unsupported_metadata(
        path,
        flags=getattr(path_stat, "st_flags", 0),
        extended_attribute_names=_list_extended_attribute_names(absolute),
    )


def _list_extended_attribute_names(path: Path) -> tuple[str, ...] | PatchResult:
    """Return xattr names or reject when metadata inspection cannot be proven."""
    try:
        return _list_extended_attributes(path)
    except (NotImplementedError, OSError) as err:
        detail = err.strerror if isinstance(err, OSError) and err.strerror is not None else type(err).__name__
        return _rejected("UNSUPPORTED_METADATA", f"extended attributes cannot be inspected safely: {path}: {detail}")


def _list_extended_attributes(path: Path) -> tuple[str, ...]:
    listxattr = getattr(os, "listxattr", None)
    if callable(listxattr):
        return tuple(sorted(listxattr(path, follow_symlinks=False)))
    if sys.platform == "darwin":
        return _list_darwin_extended_attributes(path)
    msg = "extended-attribute inspection is unavailable on this platform"
    raise NotImplementedError(msg)


def _list_darwin_extended_attributes(path: Path) -> tuple[str, ...]:
    """List macOS extended attributes without following a symlink."""
    libc = ctypes.CDLL(None, use_errno=True)
    listxattr = libc.listxattr
    listxattr.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int)
    listxattr.restype = ctypes.c_ssize_t
    encoded_path = os.fsencode(path)
    required_size = listxattr(encoded_path, None, 0, 1)
    if required_size < 0:  # pragma: no cover - Darwin fallback runs only when native os.listxattr is absent.
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()), path)
    if required_size == 0:  # pragma: no cover - Darwin fallback runs only when native os.listxattr is absent.
        return ()
    names_buffer = ctypes.create_string_buffer(required_size)
    actual_size = listxattr(encoded_path, names_buffer, required_size, 1)
    if actual_size < 0:  # pragma: no cover - Darwin fallback runs only when native os.listxattr is absent.
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()), path)
    return tuple(
        sorted(
            name.decode("utf-8", errors="surrogateescape")
            for name in names_buffer.raw[:actual_size].split(b"\0")
            if name
        )
    )


def _reject_unsupported_metadata(
    path: str,
    *,
    flags: int,
    extended_attribute_names: tuple[str, ...] | PatchResult = (),
) -> PatchResult | None:
    """Reject metadata that staged replacement cannot preserve safely."""
    if flags == 0:
        if isinstance(extended_attribute_names, PatchResult):
            return extended_attribute_names
        if not _contains_security_relevant_extended_attribute(extended_attribute_names):
            return None
        return _rejected("UNSUPPORTED_METADATA", f"ACL or security metadata cannot be preserved safely: {path}")
    return _rejected("UNSUPPORTED_METADATA", f"file flags cannot be preserved safely: {path}")


def _contains_security_relevant_extended_attribute(attribute_names: tuple[str, ...]) -> bool:
    return any(
        attribute_name in _SECURITY_RELEVANT_EXTENDED_ATTRIBUTE_NAMES
        or attribute_name.startswith(_SECURITY_RELEVANT_EXTENDED_ATTRIBUTE_PREFIXES)
        for attribute_name in attribute_names
    )
