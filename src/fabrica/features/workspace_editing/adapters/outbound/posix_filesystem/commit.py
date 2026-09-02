"""POSIX staging and commit adapter for apply-patch file operations."""

import json
import os
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.native_operations import (
    rename_no_replace,
    rename_replace,
    unlink_file,
)
from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchCommitOperation,
    PatchCommitStep,
    PatchDirectoryOutcome,
    PatchDirectoryOutcomeState,
    PatchJournalRecord,
    PatchJournalState,
    PatchMutationGuarantee,
    PatchPathEvidence,
    PatchPathOutcome,
    PatchPathOutcomeState,
    PatchPlan,
    PatchRecoveryAction,
    PatchRecoveryDecision,
    PatchRecoveryStatus,
    PatchResult,
    PatchResultStatus,
    PatchRollbackEntry,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from fabrica.features.workspace_editing.application.text_snapshot import render_added_text

DEFAULT_WORKSPACE_UMASK = 0o022
_PERMISSION_MODE_MASK = 0o777


@dataclass(frozen=True, slots=True)
class PosixPatchCommitAdapter:
    """Stage complete file payloads and execute an approved deterministic schedule."""

    workspace_root: Path
    workspace_umask: int = DEFAULT_WORKSPACE_UMASK
    after_commit_step: Callable[[PatchAction], None] | None = field(default=None, repr=False)
    _destination_parent_fds: dict[tuple[str, str], int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate the adapter-owned workspace permission policy."""
        if not 0 <= self.workspace_umask <= _PERMISSION_MODE_MASK:
            msg = "workspace_umask must be a POSIX permission mask between 0 and 0o777"
            raise ValueError(msg)

    async def prepare(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Create same-filesystem staged payloads for write and move actions."""
        journal_result = _revalidate_journal_binding(plan, journal)
        if journal_result is not None:
            return journal_result
        durable_journal_result = self._revalidate_durable_prepared_journal(plan, journal)
        if durable_journal_result is not None:
            return durable_journal_result
        stage_root = self._stage_root(journal)
        try:
            self._capture_destination_parents(plan, journal)
            stage_root.mkdir(mode=0o700, parents=True, exist_ok=False)
            _fsync_directory(stage_root.parent)
            for action in plan.actions:
                if action.kind in {PatchActionKind.ADD, PatchActionKind.UPDATE, PatchActionKind.MOVE}:
                    stage_path = _stage_path(stage_root, action)
                    stage_path.write_bytes(render_added_text(action.added_lines))
                    stage_path.chmod(self._payload_mode(plan, action))
                    _fsync_file(stage_path)
            self._prepare_rollback_backups(plan, journal)
            _fsync_directory(stage_root)
        except OSError as err:
            _remove_stage_root(stage_root)
            self._close_destination_parents(journal)
            return _rejected("IO_ERROR", f"could not stage patch payloads: {err.strerror}")
        return None

    async def commit(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult:
        """Revalidate evidence and commit staged payloads in plan order."""
        journal_result = _revalidate_journal_binding(plan, journal)
        if journal_result is not None:
            self._close_destination_parents(journal)
            return journal_result
        durable_journal_result = self._revalidate_durable_prepared_journal(plan, journal)
        if durable_journal_result is not None:
            self._close_destination_parents(journal)
            return durable_journal_result

        stage_root = self._stage_root(journal)
        validation_result = self._validate_before_commit(plan, journal, stage_root)
        if validation_result is not None:
            self._close_destination_parents(journal)
            return validation_result

        outcomes: list[PatchPathOutcome] = []
        committing_journal = _journal_with_state(journal, PatchJournalState.COMMITTING)
        try:
            _write_record(self._record_path(journal), committing_journal)
            for step in plan.commit_steps:
                if step.operation is PatchCommitOperation.CREATE_DIRECTORY:
                    continue
                committing_journal, outcome = self._commit_step(plan, stage_root, committing_journal, step)
                outcomes.append(outcome)
        except OSError:
            self._close_destination_parents(journal)
            return await self.roll_back(committing_journal)

        committed_journal = PatchJournalRecord(
            journal_digest=journal.journal_digest,
            plan_digest=journal.plan_digest,
            state=PatchJournalState.COMMITTED,
            created_directories=journal.created_directories,
            path_outcomes=tuple(outcomes),
            rollback_entries=committing_journal.rollback_entries,
            metadata=journal.metadata,
        )
        _write_record(self._record_path(journal), committed_journal)
        self._close_destination_parents(journal)

        return PatchResult(
            status=PatchResultStatus.COMMITTED,
            mutation_guarantee=PatchMutationGuarantee.COMMITTED,
            plan_digest=plan.plan_digest,
            changes=plan.changes,
            created_directories=plan.created_directories,
            directory_outcomes=journal.created_directories,
            path_outcomes=tuple(outcomes),
        )

    def _commit_step(
        self,
        plan: PatchPlan,
        stage_root: Path,
        journal: PatchJournalRecord,
        step: PatchCommitStep,
    ) -> tuple[PatchJournalRecord, PatchPathOutcome]:
        """Commit one file action after recording its reversible recovery evidence."""
        action = _action_for_step(plan, step.action_index)
        rollback_entry = _rollback_entry_for_action(self._workspace_root(), stage_root, action)
        committing_journal = _journal_with_rollback_entry(journal, rollback_entry)
        _write_record(self._record_path(journal), committing_journal)
        if step.operation is PatchCommitOperation.WRITE_FILE:
            _commit_write(self._workspace_root(), stage_root, action)
        elif step.operation is PatchCommitOperation.DELETE_FILE:
            unlink_file(self._workspace_root(), step.path)
            _fsync_directory((self._workspace_root() / step.path).parent)
        elif step.operation is PatchCommitOperation.MOVE_FILE:
            _commit_move(self._workspace_root(), stage_root, action)
        outcome = _committed_outcome(self._workspace_root(), action)
        committing_journal = _journal_with_path_outcome(committing_journal, outcome)
        _write_record(self._record_path(journal), committing_journal)
        if self.after_commit_step is not None:
            self.after_commit_step(action)
        return committing_journal, outcome

    async def roll_back(self, journal: PatchJournalRecord) -> PatchResult:
        """Roll back evidence-proven file and directory effects from a journal."""
        path_outcomes, path_recovery_required = _roll_back_files(self._workspace_root(), journal)
        directory_outcomes = _roll_back_directories(self._workspace_root(), journal)
        uncertain = tuple(
            directory
            for directory in directory_outcomes
            if directory.final_state is PatchDirectoryOutcomeState.REMOVAL_UNCERTAIN
        )
        retained = tuple(
            directory
            for directory in directory_outcomes
            if directory.final_state is PatchDirectoryOutcomeState.RETAINED_EXTERNAL_CONTENT
        )
        if path_recovery_required:
            _write_record(
                self._record_path(journal),
                _recovered_journal(journal, PatchJournalState.RECOVERY_REQUIRED, directory_outcomes, path_outcomes),
            )
            error = patch_error(
                "RECOVERY_REQUIRED",
                message="rollback retained a file path whose current state could not be proven safe to replace",
                metadata={"journal_digest": journal.journal_digest, "journal_state": journal.state.value},
            )
            return PatchResult(
                status=PatchResultStatus.RECOVERY_REQUIRED,
                mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
                plan_digest=journal.plan_digest,
                directory_outcomes=directory_outcomes,
                path_outcomes=path_outcomes,
                error=error,
            )
        if uncertain:
            _write_record(
                self._record_path(journal),
                _recovered_journal(journal, PatchJournalState.RECOVERY_REQUIRED, directory_outcomes, path_outcomes),
            )
            error = patch_error(
                "ROLLBACK_FAILED",
                message="rollback could not prove all reversible directory effects were removed safely",
                metadata={"plan_digest": journal.plan_digest},
            )
            return PatchResult(
                status=PatchResultStatus.ROLLBACK_FAILED,
                mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
                plan_digest=journal.plan_digest,
                directory_outcomes=directory_outcomes,
                path_outcomes=path_outcomes,
                error=error,
            )
        if retained:
            _write_record(
                self._record_path(journal),
                _recovered_journal(journal, PatchJournalState.RECOVERY_REQUIRED, directory_outcomes, path_outcomes),
            )
            error = patch_error(
                "CREATED_DIRECTORY_RETAINED",
                message="rollback retained independently changed directory content",
                metadata={"path": retained[0].path, "final_state": retained[0].final_state.value},
            )
            return PatchResult(
                status=PatchResultStatus.RECOVERY_REQUIRED,
                mutation_guarantee=error.mutation_guarantee,
                plan_digest=journal.plan_digest,
                directory_outcomes=directory_outcomes,
                path_outcomes=path_outcomes,
                error=error,
            )
        error = patch_error(
            "COMMIT_FAILED_ROLLED_BACK",
            message="interrupted patch preparation was rolled back safely",
        )
        _write_record(
            self._record_path(journal),
            _recovered_journal(journal, PatchJournalState.ROLLED_BACK, directory_outcomes, path_outcomes),
        )
        return PatchResult(
            status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
            mutation_guarantee=error.mutation_guarantee,
            plan_digest=journal.plan_digest,
            directory_outcomes=directory_outcomes,
            path_outcomes=path_outcomes,
            error=error,
        )

    def _payload_mode(self, plan: PatchPlan, action: PatchAction) -> int:
        if action.kind is PatchActionKind.ADD:
            return 0o666 & ~self.workspace_umask & _PERMISSION_MODE_MASK
        return _payload_mode(plan, action)

    async def inspect(self, journal: PatchJournalRecord) -> PatchRecoveryDecision:
        """Decide whether startup recovery can proceed from durable journal state."""
        if journal.state is PatchJournalState.PLANNED:
            return PatchRecoveryDecision(
                action=PatchRecoveryAction.NO_ACTION,
                status=PatchRecoveryStatus.CLEAN,
                mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
                result_status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
            )
        if journal.state in {PatchJournalState.PREPARING, PatchJournalState.PREPARED}:
            return PatchRecoveryDecision(
                action=PatchRecoveryAction.ROLL_BACK_PREPARATION,
                status=PatchRecoveryStatus.ROLLED_BACK,
                mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
                result_status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
            )
        if journal.state in {PatchJournalState.COMMITTING, PatchJournalState.ROLLING_BACK} and journal.rollback_entries:
            return PatchRecoveryDecision(
                action=PatchRecoveryAction.ROLL_BACK_COMMIT,
                status=PatchRecoveryStatus.ROLLED_BACK,
                mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
                result_status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
            )
        return PatchRecoveryDecision(
            action=PatchRecoveryAction.REQUIRE_OPERATOR_RECOVERY,
            status=PatchRecoveryStatus.RECOVERY_REQUIRED,
            mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
            result_status=PatchResultStatus.RECOVERY_REQUIRED,
        )

    async def recover(self, journal: PatchJournalRecord) -> PatchResult:
        """Perform safe startup recovery or report operator-gated recovery."""
        decision = await self.inspect(journal)
        if decision.action is PatchRecoveryAction.NO_ACTION:
            _write_record(
                self._record_path(journal),
                _journal_with_state(journal, PatchJournalState.ROLLED_BACK),
            )
            error = patch_error(
                "COMMIT_FAILED_ROLLED_BACK",
                message="interrupted patch journal had no visible effects",
            )
            return PatchResult(
                status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
                mutation_guarantee=error.mutation_guarantee,
                plan_digest=journal.plan_digest,
                directory_outcomes=journal.created_directories,
                path_outcomes=journal.path_outcomes,
                error=error,
            )
        if decision.action is PatchRecoveryAction.ROLL_BACK_PREPARATION:
            return await self.roll_back(journal)
        if decision.action is PatchRecoveryAction.ROLL_BACK_COMMIT:
            return await self.roll_back(journal)
        error = patch_error(
            "RECOVERY_REQUIRED",
            message="incomplete commit journal requires operator recovery",
            metadata={"journal_digest": journal.journal_digest, "journal_state": journal.state.value},
        )
        return PatchResult(
            status=PatchResultStatus.RECOVERY_REQUIRED,
            mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
            plan_digest=journal.plan_digest,
            directory_outcomes=journal.created_directories,
            path_outcomes=journal.path_outcomes,
            error=error,
        )

    def _validate_before_commit(
        self, plan: PatchPlan, journal: PatchJournalRecord, stage_root: Path
    ) -> PatchResult | None:
        return (
            self._revalidate_destination_parents(plan, journal)
            or _revalidate_plan(self._workspace_root(), plan)
            or _revalidate_staging(stage_root, plan, self._payload_mode)
        )

    def _revalidate_durable_prepared_journal(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Ensure durable recovery evidence still binds this plan before file work."""
        try:
            payload = json.loads(self._record_path(journal).read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return _rejected("STALE_PLAN", "durable journal is unavailable or invalid before file commit")
        if (
            payload.get("journal_digest") != journal.journal_digest
            or payload.get("plan_digest") != plan.plan_digest
            or payload.get("state") != PatchJournalState.PREPARED.value
        ):
            return _rejected("STALE_PLAN", "durable journal no longer authorizes the approved file commit")
        return None

    def _capture_destination_parents(self, plan: PatchPlan, journal: PatchJournalRecord) -> None:
        for action in plan.actions:
            destination_path = _destination_path(action)
            if destination_path is None:
                continue
            parent = destination_path.rpartition("/")[0]
            absolute = self._workspace_root() if not parent else self._workspace_root() / parent
            key = (journal.journal_digest, parent)
            if absolute.is_dir() and key not in self._destination_parent_fds:
                self._destination_parent_fds[key] = os.open(absolute, os.O_RDONLY)

    def _revalidate_destination_parents(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        for action in plan.actions:
            destination_path = _destination_path(action)
            if destination_path is None:
                continue
            parent = destination_path.rpartition("/")[0]
            descriptor = self._destination_parent_fds.get((journal.journal_digest, parent))
            if descriptor is None:
                continue
            absolute = self._workspace_root() if not parent else self._workspace_root() / parent
            try:
                descriptor_stat = os.fstat(descriptor)
                current_stat = absolute.stat()
            except OSError:
                return _rejected("STALE_PLAN", f"destination ancestor changed before commit: {destination_path}")
            if (descriptor_stat.st_dev, descriptor_stat.st_ino) != (current_stat.st_dev, current_stat.st_ino):
                return _rejected("STALE_PLAN", f"destination ancestor changed before commit: {destination_path}")
        return None

    def _close_destination_parents(self, journal: PatchJournalRecord) -> None:
        keys = [key for key in self._destination_parent_fds if key[0] == journal.journal_digest]
        for key in keys:
            os.close(self._destination_parent_fds.pop(key))

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

    def _record_path(self, journal: PatchJournalRecord) -> Path:
        return (
            self._workspace_root()
            / ".fabrica"
            / "apply-patch"
            / "journal"
            / f"{journal.journal_digest.removeprefix('sha256:')}.json"
        )

    def _backup_root(self, journal: PatchJournalRecord) -> Path:
        return self._stage_root(journal) / "backups"

    def _prepare_rollback_backups(self, plan: PatchPlan, journal: PatchJournalRecord) -> None:
        backup_root = self._backup_root(journal)
        for action in plan.actions:
            if action.kind is PatchActionKind.ADD:
                continue
            backup_path = _backup_path(backup_root, action)
            backup_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copyfile(self._workspace_root() / action.path, backup_path)
            backup_path.chmod(self._payload_mode(plan, action))
            _fsync_file(backup_path)
        if backup_root.exists():
            _fsync_directory(backup_root)


def _revalidate_journal_binding(plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
    if journal.plan_digest != plan.plan_digest:
        return _rejected("STALE_PLAN", "journal plan digest does not match the approved patch plan")
    if journal.journal_digest != _journal_digest(plan.plan_digest):
        return _rejected("STALE_PLAN", "journal digest does not match the approved patch plan")
    return None


def _journal_with_state(journal: PatchJournalRecord, state: PatchJournalState) -> PatchJournalRecord:
    return PatchJournalRecord(
        journal_digest=journal.journal_digest,
        plan_digest=journal.plan_digest,
        state=state,
        created_directories=journal.created_directories,
        path_outcomes=journal.path_outcomes,
        rollback_entries=journal.rollback_entries,
        metadata=journal.metadata,
    )


def _recovered_journal(
    journal: PatchJournalRecord,
    state: PatchJournalState,
    directory_outcomes: tuple[PatchDirectoryOutcome, ...],
    path_outcomes: tuple[PatchPathOutcome, ...],
) -> PatchJournalRecord:
    return PatchJournalRecord(
        journal_digest=journal.journal_digest,
        plan_digest=journal.plan_digest,
        state=state,
        created_directories=directory_outcomes,
        path_outcomes=path_outcomes,
        rollback_entries=journal.rollback_entries,
        metadata=journal.metadata,
    )


def _journal_with_rollback_entry(journal: PatchJournalRecord, entry: PatchRollbackEntry) -> PatchJournalRecord:
    return PatchJournalRecord(
        journal_digest=journal.journal_digest,
        plan_digest=journal.plan_digest,
        state=journal.state,
        created_directories=journal.created_directories,
        path_outcomes=journal.path_outcomes,
        rollback_entries=(*journal.rollback_entries, entry),
        metadata=journal.metadata,
    )


def _journal_with_path_outcome(journal: PatchJournalRecord, outcome: PatchPathOutcome) -> PatchJournalRecord:
    return PatchJournalRecord(
        journal_digest=journal.journal_digest,
        plan_digest=journal.plan_digest,
        state=journal.state,
        created_directories=journal.created_directories,
        path_outcomes=(*journal.path_outcomes, outcome),
        rollback_entries=journal.rollback_entries,
        metadata=journal.metadata,
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


def _revalidate_staging(
    stage_root: Path,
    plan: PatchPlan,
    payload_mode: Callable[[PatchPlan, PatchAction], int],
) -> PatchResult | None:
    for action in plan.actions:
        if action.kind not in {PatchActionKind.ADD, PatchActionKind.UPDATE, PatchActionKind.MOVE}:
            continue
        stage_path = _stage_path(stage_root, action)
        try:
            path_stat = stage_path.stat()
        except FileNotFoundError:
            return _rejected("STALE_PLAN", f"staged payload missing before commit: {action.path}")
        expected_payload = render_added_text(action.added_lines)
        if not stage_path.is_file() or path_stat.st_size != len(expected_payload):
            return _rejected("STALE_PLAN", f"staged payload changed before commit: {action.path}")
        if _digest_bytes(stage_path.read_bytes()) != _digest_bytes(expected_payload):
            return _rejected("STALE_PLAN", f"staged payload content changed before commit: {action.path}")
        if stat.S_IMODE(path_stat.st_mode) != payload_mode(plan, action):
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
    staged_path = _stage_path(stage_root, action).relative_to(root).as_posix()
    if action.kind is PatchActionKind.ADD:
        rename_no_replace(root, staged_path, action.path)
    else:
        rename_replace(root, staged_path, action.path)
    destination = root / action.path
    _fsync_file(destination)
    _fsync_directory(destination.parent)


def _commit_move(root: Path, stage_root: Path, action: PatchAction) -> None:
    if action.destination_path is None:
        msg = "move actions must include a destination path"
        raise ValueError(msg)
    staged_path = _stage_path(stage_root, action).relative_to(root).as_posix()
    rename_no_replace(root, staged_path, action.destination_path)
    unlink_file(root, action.path)
    destination = root / action.destination_path
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


def _roll_back_directories(root: Path, journal: PatchJournalRecord) -> tuple[PatchDirectoryOutcome, ...]:
    outcomes_by_path = {directory.path: directory for directory in journal.created_directories}
    for directory in sorted(journal.created_directories, key=lambda item: item.path.count("/"), reverse=True):
        if directory.final_state is not PatchDirectoryOutcomeState.CREATED:
            continue
        outcomes_by_path[directory.path] = _roll_back_directory(root, directory)
    return tuple(outcomes_by_path[directory.path] for directory in journal.created_directories)


def _roll_back_directory(root: Path, directory: PatchDirectoryOutcome) -> PatchDirectoryOutcome:
    absolute = root / directory.path
    try:
        path_stat = absolute.lstat()
    except FileNotFoundError:
        return _directory_with_state(directory, PatchDirectoryOutcomeState.REMOVED)
    if not stat.S_ISDIR(path_stat.st_mode) or _directory_identity_digest(path_stat) != directory.identity_digest:
        return _directory_with_state(directory, PatchDirectoryOutcomeState.REMOVAL_UNCERTAIN)
    try:
        absolute.rmdir()
        _fsync_directory(absolute.parent)
    except OSError:
        return _directory_with_state(directory, PatchDirectoryOutcomeState.RETAINED_EXTERNAL_CONTENT)
    return _directory_with_state(directory, PatchDirectoryOutcomeState.REMOVED)


def _directory_with_state(directory: PatchDirectoryOutcome, state: PatchDirectoryOutcomeState) -> PatchDirectoryOutcome:
    return PatchDirectoryOutcome(
        path=directory.path,
        planned_effect=directory.planned_effect,
        final_state=state,
        reason=directory.reason,
        identity_digest=directory.identity_digest,
    )


def _stage_path(stage_root: Path, action: PatchAction) -> Path:
    return stage_root / f"{action.index:06d}.payload"


def _backup_path(backup_root: Path, action: PatchAction) -> Path:
    return backup_root / f"{action.index:06d}.preimage"


def _rollback_entry_for_action(root: Path, stage_root: Path, action: PatchAction) -> PatchRollbackEntry:
    postimage_path = action.destination_path if action.kind is PatchActionKind.MOVE else action.path
    if postimage_path is None:
        msg = "move actions must include a destination path"
        raise ValueError(msg)
    postimage = (
        PatchPathEvidence(path=postimage_path, exists=False)
        if action.kind is PatchActionKind.DELETE
        else _staged_postimage(postimage_path, _stage_path(stage_root, action), action)
    )
    backup_path = None if action.kind is PatchActionKind.ADD else _backup_path(stage_root / "backups", action)
    return PatchRollbackEntry(
        path=action.path,
        operation=action.kind,
        destination_path=action.destination_path,
        backup_path=str(backup_path.relative_to(root)) if backup_path is not None else None,
        preimage=_snapshot_path(root, action.path),
        postimage=postimage,
    )


def _staged_postimage(path: str, stage_path: Path, action: PatchAction) -> PatchPathEvidence:
    payload = stage_path.read_bytes()
    return PatchPathEvidence(
        path=path,
        exists=True,
        content_digest=_digest_bytes(payload),
        metadata={"mode": stat.S_IMODE(stage_path.stat().st_mode), "operation": action.kind.value},
    )


def _roll_back_files(root: Path, journal: PatchJournalRecord) -> tuple[tuple[PatchPathOutcome, ...], bool]:
    outcomes: list[PatchPathOutcome] = []
    recovery_required = False
    for entry in reversed(journal.rollback_entries):
        outcome, entry_recovery_required = _roll_back_file(root, entry)
        outcomes.append(outcome)
        recovery_required = recovery_required or entry_recovery_required
    return tuple(reversed(outcomes)), recovery_required


def _roll_back_file(root: Path, entry: PatchRollbackEntry) -> tuple[PatchPathOutcome, bool]:
    current_path = entry.destination_path if entry.operation is PatchActionKind.MOVE else entry.path
    if current_path is None or entry.postimage is None or not _matches_postimage(root, current_path, entry.postimage):
        return _rollback_unknown_outcome(entry), True
    try:
        if entry.operation is PatchActionKind.ADD:
            (root / current_path).unlink()
            _fsync_directory((root / current_path).parent)
        else:
            if entry.backup_path is None:
                return _rollback_unknown_outcome(entry), True
            backup_path = root / entry.backup_path
            if not _matches_preimage_file(backup_path, entry.preimage):
                return _rollback_unknown_outcome(entry), True
            backup_path.replace(root / entry.path)
            _fsync_file(root / entry.path)
            _fsync_directory((root / entry.path).parent)
            if entry.operation is PatchActionKind.MOVE:
                (root / current_path).unlink()
                _fsync_directory((root / current_path).parent)
    except OSError:
        return _rollback_unknown_outcome(entry), True
    return (
        PatchPathOutcome(
            path=entry.path,
            planned_operation=entry.operation,
            final_state=PatchPathOutcomeState.ROLLED_BACK,
            destination_path=entry.destination_path,
            evidence=_snapshot_path(root, entry.path),
        ),
        False,
    )


def _matches_postimage(root: Path, path: str, expected: PatchPathEvidence) -> bool:
    current = _snapshot_path(root, path)
    if not expected.exists:
        return not current.exists
    return (
        current.exists
        and current.content_digest == expected.content_digest
        and current.metadata.get("mode") == expected.metadata.get("mode")
    )


def _matches_preimage_file(path: Path, expected: PatchPathEvidence) -> bool:
    if not path.is_file() or not expected.exists:
        return False
    return _digest_bytes(path.read_bytes()) == expected.content_digest


def _rollback_unknown_outcome(entry: PatchRollbackEntry) -> PatchPathOutcome:
    return PatchPathOutcome(
        path=entry.path,
        planned_operation=entry.operation,
        final_state=PatchPathOutcomeState.UNKNOWN,
        destination_path=entry.destination_path,
        evidence=entry.postimage,
    )


def _remove_stage_root(stage_root: Path) -> None:
    """Remove adapter-owned incomplete staging artifacts after a pre-commit failure."""
    try:
        shutil.rmtree(stage_root)
        _fsync_directory(stage_root.parent)
    except OSError:
        return


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


def _journal_digest(plan_digest: str) -> str:
    return "sha256:" + sha256(f"apply-patch-journal:{plan_digest}".encode()).hexdigest()


def _write_record(path: Path, record: PatchJournalRecord) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "created_directories": [
            {
                "final_state": directory.final_state.value,
                "identity_digest": directory.identity_digest,
                "path": directory.path,
                "planned_effect": directory.planned_effect.value,
                "reason": directory.reason,
            }
            for directory in record.created_directories
        ],
        "journal_digest": record.journal_digest,
        "metadata": dict(record.metadata),
        "path_outcomes": [_path_outcome_payload(outcome) for outcome in record.path_outcomes],
        "plan_digest": record.plan_digest,
        "rollback_entries": [_rollback_entry_payload(entry) for entry in record.rollback_entries],
        "state": record.state.value,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_bytes(encoded)
    _fsync_file(tmp_path)
    tmp_path.replace(path)
    _fsync_directory(path.parent)


def _path_outcome_payload(outcome: PatchPathOutcome) -> dict[str, object]:
    payload: dict[str, object] = {
        "final_state": outcome.final_state.value,
        "path": outcome.path,
        "planned_operation": outcome.planned_operation.value,
    }
    if outcome.destination_path is not None:
        payload["destination_path"] = outcome.destination_path
    if outcome.evidence is not None:
        payload["evidence"] = {
            "content_digest": outcome.evidence.content_digest,
            "exists": outcome.evidence.exists,
            "identity_digest": outcome.evidence.identity_digest,
            "metadata": dict(outcome.evidence.metadata),
            "path": outcome.evidence.path,
        }
    return payload


def _rollback_entry_payload(entry: PatchRollbackEntry) -> dict[str, object]:
    payload: dict[str, object] = {
        "backup_path": entry.backup_path,
        "destination_path": entry.destination_path,
        "operation": entry.operation.value,
        "path": entry.path,
        "preimage": _path_evidence_payload(entry.preimage),
    }
    if entry.postimage is not None:
        payload["postimage"] = _path_evidence_payload(entry.postimage)
    return payload


def _path_evidence_payload(evidence: PatchPathEvidence) -> dict[str, object]:
    return {
        "content_digest": evidence.content_digest,
        "exists": evidence.exists,
        "identity_digest": evidence.identity_digest,
        "metadata": dict(evidence.metadata),
        "path": evidence.path,
    }


def _rejected(code: str, message: str) -> PatchResult:
    error = patch_error(code, message=message)
    return PatchResult(status=PatchResultStatus.REJECTED, mutation_guarantee=error.mutation_guarantee, error=error)


__all__ = ["PosixPatchCommitAdapter"]
