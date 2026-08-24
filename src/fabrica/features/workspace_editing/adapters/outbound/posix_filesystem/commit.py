"""POSIX staging and commit adapter for apply-patch file operations."""

import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchCommitOperation,
    PatchJournalRecord,
    PatchMutationGuarantee,
    PatchPathEvidence,
    PatchPathOutcome,
    PatchPathOutcomeState,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from fabrica.features.workspace_editing.application.text_snapshot import render_added_text


@dataclass(frozen=True, slots=True)
class PosixPatchCommitAdapter:
    """Stage complete file payloads and execute an approved deterministic schedule."""

    workspace_root: Path

    async def prepare(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Create same-filesystem staged payloads for write and move actions."""
        stage_root = self._stage_root(journal)
        try:
            stage_root.mkdir(mode=0o700, parents=True, exist_ok=False)
            _fsync_directory(stage_root.parent)
            for action in plan.actions:
                if action.kind in {PatchActionKind.ADD, PatchActionKind.UPDATE, PatchActionKind.MOVE}:
                    stage_path = _stage_path(stage_root, action)
                    stage_path.write_bytes(render_added_text(action.added_lines))
                    stage_path.chmod(_payload_mode(plan, action))
                    _fsync_file(stage_path)
            _fsync_directory(stage_root)
        except OSError as err:
            return _rejected("IO_ERROR", f"could not stage patch payloads: {err.strerror}")
        return None

    async def commit(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult:
        """Revalidate evidence and commit staged payloads in plan order."""
        stale_result = _revalidate_plan(self._workspace_root(), plan)
        if stale_result is not None:
            return stale_result

        stage_root = self._stage_root(journal)
        staging_result = _revalidate_staging(stage_root, plan)
        if staging_result is not None:
            return staging_result

        outcomes: list[PatchPathOutcome] = []
        try:
            for step in plan.commit_steps:
                if step.operation is PatchCommitOperation.CREATE_DIRECTORY:
                    continue
                action = _action_for_step(plan, step.action_index)
                if step.operation is PatchCommitOperation.WRITE_FILE:
                    _commit_write(self._workspace_root(), stage_root, action)
                elif step.operation is PatchCommitOperation.DELETE_FILE:
                    (self._workspace_root() / step.path).unlink()
                elif step.operation is PatchCommitOperation.MOVE_FILE:
                    _commit_move(self._workspace_root(), stage_root, action)
                outcomes.append(_committed_outcome(self._workspace_root(), action))
        except OSError as err:
            error = patch_error(
                "INDETERMINATE_COMMIT_STATE",
                message=f"commit operation failed: {err.strerror}",
                metadata={"plan_digest": plan.plan_digest},
            )
            return PatchResult(
                status=PatchResultStatus.INDETERMINATE_COMMIT_STATE,
                mutation_guarantee=error.mutation_guarantee,
                plan_digest=plan.plan_digest,
                changes=plan.changes,
                created_directories=plan.created_directories,
                directory_outcomes=journal.created_directories,
                path_outcomes=tuple(outcomes),
                error=error,
            )

        return PatchResult(
            status=PatchResultStatus.COMMITTED,
            mutation_guarantee=PatchMutationGuarantee.COMMITTED,
            plan_digest=plan.plan_digest,
            changes=plan.changes,
            created_directories=plan.created_directories,
            directory_outcomes=journal.created_directories,
            path_outcomes=tuple(outcomes),
        )

    def _workspace_root(self) -> Path:
        return self.workspace_root.resolve(strict=True)

    def _stage_root(self, journal: PatchJournalRecord) -> Path:
        return (
            self._workspace_root()
            / ".fabrica"
            / "apply-patch"
            / "stage"
            / journal.journal_digest.removeprefix("sha256:")
        )


def _revalidate_plan(root: Path, plan: PatchPlan) -> PatchResult | None:
    created_directory_paths = frozenset(directory.path for directory in plan.created_directories)
    for evidence in plan.path_evidence:
        source_result = _revalidate_path_evidence(root, evidence, created_directory_paths)
        if source_result is not None:
            return source_result
    for action in plan.actions:
        destination_result = _revalidate_destination_safety(root, plan, action, created_directory_paths)
        if destination_result is not None:
            return destination_result
    return None


def _revalidate_path_evidence(
    root: Path, evidence: PatchPathEvidence, created_directory_paths: frozenset[str]
) -> PatchResult | None:
    current = _snapshot_path(root, evidence.path)
    if current.exists != evidence.exists:
        return _rejected("STALE_PLAN", f"path existence changed before commit: {evidence.path}")
    expected_ancestor_digest = evidence.metadata.get("ancestor_identity_digest")
    current_ancestor_digest = _ancestor_digest(root, evidence.path, excluded_directories=created_directory_paths)
    if expected_ancestor_digest is not None and current_ancestor_digest != expected_ancestor_digest:
        return _rejected("STALE_PLAN", f"path ancestor changed before commit: {evidence.path}")
    if evidence.exists and current.content_digest != evidence.content_digest:
        return _rejected("STALE_PLAN", f"path content changed before commit: {evidence.path}")
    if evidence.exists and current.identity_digest != evidence.identity_digest:
        return _rejected("STALE_PLAN", f"path identity changed before commit: {evidence.path}")
    return None


def _revalidate_destination_safety(
    root: Path, plan: PatchPlan, action: PatchAction, created_directory_paths: frozenset[str]
) -> PatchResult | None:
    destination_path = _destination_path(action)
    if destination_path is None:
        return None
    destination_evidence = _evidence_for_path(plan, destination_path)
    if destination_evidence is None:
        return _rejected("STALE_PLAN", f"destination evidence missing before commit: {destination_path}")
    current_destination = _snapshot_path(root, destination_path)
    if current_destination.exists:
        return _rejected("STALE_PLAN", f"destination appeared before commit: {destination_path}")
    expected_ancestor_digest = destination_evidence.metadata.get("ancestor_identity_digest")
    current_ancestor_digest = _ancestor_digest(root, destination_path, excluded_directories=created_directory_paths)
    if expected_ancestor_digest is not None and current_ancestor_digest != expected_ancestor_digest:
        return _rejected("STALE_PLAN", f"destination ancestor changed before commit: {destination_path}")
    return None


def _destination_path(action: PatchAction) -> str | None:
    if action.kind is PatchActionKind.ADD:
        return action.path
    if action.kind is PatchActionKind.MOVE:
        return action.destination_path
    return None


def _evidence_for_path(plan: PatchPlan, path: str) -> PatchPathEvidence | None:
    return next((item for item in plan.path_evidence if item.path == path), None)


def _revalidate_staging(stage_root: Path, plan: PatchPlan) -> PatchResult | None:
    for action in plan.actions:
        if action.kind not in {PatchActionKind.ADD, PatchActionKind.UPDATE, PatchActionKind.MOVE}:
            continue
        stage_path = _stage_path(stage_root, action)
        try:
            path_stat = stage_path.stat()
        except FileNotFoundError:
            return _rejected("STALE_PLAN", f"staged payload missing before commit: {action.path}")
        if not stage_path.is_file() or path_stat.st_size != len(render_added_text(action.added_lines)):
            return _rejected("STALE_PLAN", f"staged payload changed before commit: {action.path}")
        if stat.S_IMODE(path_stat.st_mode) != _payload_mode(plan, action):
            return _rejected("STALE_PLAN", f"staged payload mode changed before commit: {action.path}")
    return None


def _payload_mode(plan: PatchPlan, action: PatchAction) -> int:
    if action.kind is PatchActionKind.ADD:
        return 0o644
    evidence = _evidence_for_path(plan, action.path)
    if evidence is None:
        return 0o644
    mode = evidence.metadata.get("mode")
    if not isinstance(mode, int):
        return 0o644
    return stat.S_IMODE(mode)


def _snapshot_path(root: Path, path: str) -> PatchPathEvidence:
    absolute = root / path
    try:
        path_stat = absolute.lstat()
    except FileNotFoundError:
        return PatchPathEvidence(
            path=path,
            exists=False,
            metadata={"ancestor_identity_digest": _ancestor_digest(root, path)},
        )
    content = absolute.read_bytes()
    return PatchPathEvidence(
        path=path,
        exists=True,
        content_digest=_digest_bytes(content),
        identity_digest=_identity_digest(path_stat),
        metadata={
            "ancestor_identity_digest": _ancestor_digest(root, path),
            "mode": stat.S_IMODE(path_stat.st_mode),
        },
    )


def _ancestor_digest(root: Path, path: str, excluded_directories: frozenset[str] = frozenset()) -> str:
    parent = path.rpartition("/")[0]
    while parent in excluded_directories:
        parent = parent.rpartition("/")[0]
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


def _action_for_step(plan: PatchPlan, action_index: int | None) -> PatchAction:
    if action_index is None:
        msg = "file commit steps must include an action index"
        raise ValueError(msg)
    return next(action for action in plan.actions if action.index == action_index)


def _commit_write(root: Path, stage_root: Path, action: PatchAction) -> None:
    destination = root / action.path
    _stage_path(stage_root, action).replace(destination)
    _fsync_file(destination)
    _fsync_directory(destination.parent)


def _commit_move(root: Path, stage_root: Path, action: PatchAction) -> None:
    if action.destination_path is None:
        msg = "move actions must include a destination path"
        raise ValueError(msg)
    (root / action.path).unlink()
    destination = root / action.destination_path
    _stage_path(stage_root, action).replace(destination)
    _fsync_file(destination)
    _fsync_directory(destination.parent)
    _fsync_directory((root / action.path).parent)


def _committed_outcome(root: Path, action: PatchAction) -> PatchPathOutcome:
    outcome_path = action.destination_path if action.kind is PatchActionKind.MOVE else action.path
    if outcome_path is None:
        outcome_path = action.path
    return PatchPathOutcome(
        path=action.path,
        planned_operation=action.kind,
        final_state=PatchPathOutcomeState.COMMITTED,
        destination_path=action.destination_path,
        evidence=_snapshot_path(root, outcome_path),
    )


def _stage_path(stage_root: Path, action: PatchAction) -> Path:
    return stage_root / f"{action.index:06d}.payload"


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    directory_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _identity_digest(path_stat: os.stat_result) -> str:
    payload = f"{path_stat.st_dev}:{path_stat.st_ino}:{path_stat.st_mode}:{path_stat.st_nlink}"
    return _digest_bytes(payload.encode("utf-8"))


def _digest_bytes(content: bytes) -> str:
    return "sha256:" + sha256(content).hexdigest()


def _rejected(code: str, message: str) -> PatchResult:
    error = patch_error(code, message=message)
    return PatchResult(status=PatchResultStatus.REJECTED, mutation_guarantee=error.mutation_guarantee, error=error)


__all__ = ["PosixPatchCommitAdapter"]
