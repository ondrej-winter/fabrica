"""POSIX snapshot and capability adapter for apply-patch planning."""

import os
import stat
import sys
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

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


@dataclass(frozen=True, slots=True)
class PosixPatchWorkspaceSnapshotAdapter:
    """Build side-effect-free path evidence using POSIX filesystem facts."""

    workspace_root: Path
    require_production_capabilities: bool = True

    async def verify_workspace_capabilities(self) -> PatchResult | None:
        """Fail closed until production no-replace rename and helper ownership exist."""
        if sys.platform not in {"darwin", "linux"} or self.require_production_capabilities:
            return _rejected(
                "UNSUPPORTED_FILESYSTEM_GUARANTEE",
                "workspace filesystem mutation guarantees are not available",
            )
        try:
            root_stat = self.workspace_root.stat()
        except OSError as err:
            return _rejected("IO_ERROR", f"could not stat workspace root: {err.strerror}")
        if not stat.S_ISDIR(root_stat.st_mode):
            return _rejected("PARENT_PATH_NOT_DIRECTORY", "workspace root must be a directory")
        return None

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
            alias_result = _reject_path_alias(root, action.path)
            if alias_result is not None:
                return alias_result

            source_result = _snapshot_action_source(root, action)
            if isinstance(source_result, PatchResult):
                return source_result
            if source_result is not None:
                evidence_by_path[action.path] = source_result

            destination = action.path if action.kind is PatchActionKind.ADD else action.destination_path
            if destination is not None:
                alias_result = _reject_path_alias(root, destination)
                if alias_result is not None:
                    return alias_result
                destination_result = _snapshot_destination(root, action.kind, destination)
                if isinstance(destination_result, PatchResult):
                    return destination_result
                evidence_by_path[destination] = destination_result

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
    return None


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

    unsupported_result = _unsupported_existing_path_result(path_stat, path)
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


def _rejected(code: str, message: str) -> PatchResult:
    error = patch_error(code, message=message)
    return PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        error=error,
    )


__all__ = ["PosixPatchWorkspaceSnapshotAdapter"]


def _unsupported_existing_path_result(path_stat: os.stat_result, path: str) -> PatchResult | None:
    if stat.S_ISLNK(path_stat.st_mode):
        return _rejected("SYMLINK_PATH_UNSUPPORTED", f"symlink paths are unsupported: {path}")
    if not stat.S_ISREG(path_stat.st_mode):
        code = "PARENT_PATH_NOT_DIRECTORY" if stat.S_ISDIR(path_stat.st_mode) else "SPECIAL_FILE_UNSUPPORTED"
        return _rejected(code, f"path is not a regular file: {path}")
    if path_stat.st_nlink != 1:
        return _rejected("MULTIPLE_HARD_LINKS_UNSUPPORTED", f"multiple hard links are unsupported: {path}")
    return None
