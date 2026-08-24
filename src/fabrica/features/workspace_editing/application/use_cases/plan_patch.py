"""Pure immutable planning for parsed apply-patch actions."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchApprovalPreview,
    PatchChangeSummary,
    PatchCommitOperation,
    PatchCommitStep,
    PatchDirectoryOutcome,
    PatchDirectoryOutcomeState,
    PatchDirectoryPlannedEffect,
    PatchLimits,
    PatchMutationGuarantee,
    PatchPathEvidence,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error

PLAN_DIGEST_PREFIX = "sha256:"
PLACEHOLDER_PLAN_DIGEST = PLAN_DIGEST_PREFIX + "0" * 64


@dataclass(frozen=True, slots=True)
class PatchPlanningSnapshot:
    """Adapter-supplied path facts used by pure planning without filesystem I/O."""

    evidence_by_path: Mapping[str, PatchPathEvidence] = field(default_factory=dict)
    existing_directories: frozenset[str] = field(default_factory=lambda: frozenset({""}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_by_path", dict(self.evidence_by_path))
        object.__setattr__(self, "existing_directories", frozenset(self.existing_directories | {""}))


@dataclass(frozen=True, slots=True)
class PlanPatchResult:
    """Result of converting parsed actions and snapshot facts into an immutable plan."""

    plan: PatchPlan | None
    result: PatchResult


class PlanPatch:
    """Build an immutable, approval-ready apply-patch plan without touching files."""

    def plan(
        self,
        actions: tuple[PatchAction, ...],
        snapshot: PatchPlanningSnapshot,
        limits: PatchLimits | None = None,
    ) -> PlanPatchResult:
        """Validate parsed actions and return a digest-bound plan or rejection."""
        active_limits = limits or PatchLimits()
        rejection = _validate_global_disjointness(actions)
        if rejection is not None:
            return rejection

        created_directories = _derive_created_directories(actions, snapshot)
        commit_steps = _commit_steps(actions, created_directories)
        changes = tuple(_change_summary(action) for action in actions)
        evidence = tuple(snapshot.evidence_by_path[path] for path in sorted(snapshot.evidence_by_path))
        preview_text = _approval_preview_text(changes, created_directories)
        if len(preview_text) > active_limits.max_output_chars:
            return _rejected("LIMIT_EXCEEDED", "approval preview exceeds the configured output limit")
        preview = PatchApprovalPreview(text=preview_text)

        digest_payload = PatchPlan(
            plan_digest=PLACEHOLDER_PLAN_DIGEST,
            actions=actions,
            changes=changes,
            created_directories=created_directories,
            path_evidence=evidence,
            commit_steps=commit_steps,
            approval_preview=preview,
        )
        digest = _plan_digest(digest_payload)
        plan = PatchPlan(
            plan_digest=digest,
            actions=actions,
            changes=changes,
            created_directories=created_directories,
            path_evidence=evidence,
            commit_steps=commit_steps,
            approval_preview=preview,
        )
        return PlanPatchResult(
            plan=plan,
            result=PatchResult(
                status=PatchResultStatus.COMMITTED,
                mutation_guarantee=PatchMutationGuarantee.COMMITTED,
                plan_digest=digest,
                changes=changes,
                created_directories=created_directories,
            ),
        )


def _validate_global_disjointness(actions: tuple[PatchAction, ...]) -> PlanPatchResult | None:
    seen_sources: set[str] = set()
    seen_destinations: set[str] = set()
    for action in actions:
        if action.kind in {PatchActionKind.UPDATE, PatchActionKind.DELETE, PatchActionKind.MOVE}:
            if action.path in seen_sources:
                return _rejected("DUPLICATE_ACTION", f"path {action.path} is modified more than once")
            if action.path in seen_destinations:
                return _rejected("DESTINATION_COLLISION", f"path {action.path} collides with another destination")
            seen_sources.add(action.path)

        if action.kind in {PatchActionKind.ADD, PatchActionKind.MOVE}:
            destination = action.destination_path if action.kind is PatchActionKind.MOVE else action.path
            if destination is None:
                msg = "move action unexpectedly omitted its destination"
                raise RuntimeError(msg)
            if destination in seen_destinations or destination in seen_sources:
                return _rejected("DESTINATION_COLLISION", f"destination {destination} collides with another path")
            seen_destinations.add(destination)
    return None


def _derive_created_directories(
    actions: tuple[PatchAction, ...], snapshot: PatchPlanningSnapshot
) -> tuple[PatchDirectoryOutcome, ...]:
    directories: set[str] = set()
    for action in actions:
        destination = action.destination_path if action.kind is PatchActionKind.MOVE else action.path
        if action.kind in {PatchActionKind.ADD, PatchActionKind.MOVE}:
            if destination is None:
                msg = "move action unexpectedly omitted its destination"
                raise RuntimeError(msg)
            directories.update(_missing_parent_chain(destination, snapshot.existing_directories))
    return tuple(
        PatchDirectoryOutcome(
            path=path,
            planned_effect=PatchDirectoryPlannedEffect.CREATE_DIRECTORY,
            final_state=PatchDirectoryOutcomeState.NOT_CREATED,
            reason="parent_for_destination",
        )
        for path in sorted(directories, key=lambda value: (value.count("/"), value))
    )


def _missing_parent_chain(path: str, existing_directories: frozenset[str]) -> tuple[str, ...]:
    parent = path.rpartition("/")[0]
    if not parent:
        return ()
    parts = parent.split("/")
    chain = tuple("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    return tuple(directory for directory in chain if directory not in existing_directories)


def _commit_steps(
    actions: tuple[PatchAction, ...], created_directories: tuple[PatchDirectoryOutcome, ...]
) -> tuple[PatchCommitStep, ...]:
    steps = [
        PatchCommitStep(operation=PatchCommitOperation.CREATE_DIRECTORY, path=directory.path)
        for directory in created_directories
    ]
    for action in actions:
        if action.kind in {PatchActionKind.ADD, PatchActionKind.UPDATE}:
            steps.append(PatchCommitStep(PatchCommitOperation.WRITE_FILE, action.path, action_index=action.index))
        elif action.kind is PatchActionKind.DELETE:
            steps.append(PatchCommitStep(PatchCommitOperation.DELETE_FILE, action.path, action_index=action.index))
        else:
            steps.append(
                PatchCommitStep(
                    PatchCommitOperation.MOVE_FILE,
                    action.path,
                    action_index=action.index,
                    destination_path=action.destination_path,
                )
            )
    return tuple(steps)


def _approval_preview_text(
    changes: tuple[PatchChangeSummary, ...], created_directories: tuple[PatchDirectoryOutcome, ...]
) -> str:
    lines = ["Apply patch plan:"]
    lines.extend(f"- create directory {directory.path}" for directory in created_directories)
    for change in changes:
        destination = f" -> {change.destination_path}" if change.destination_path else ""
        lines.append(f"- {change.operation.value} {change.path}{destination}")
    return "\n".join(lines)


def _change_summary(action: PatchAction) -> PatchChangeSummary:
    return PatchChangeSummary(
        index=action.index,
        operation=action.kind,
        path=action.path,
        destination_path=action.destination_path,
        hunks=len(action.hunks),
    )


def _plan_digest(plan: PatchPlan) -> str:
    payload = {
        "actions": [repr(action) for action in plan.actions],
        "changes": [repr(change) for change in plan.changes],
        "commit_steps": [repr(step) for step in plan.commit_steps],
        "created_directories": [repr(directory) for directory in plan.created_directories],
        "evidence": [repr(item) for item in plan.path_evidence],
        "preview": plan.approval_preview.text if plan.approval_preview is not None else None,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return PLAN_DIGEST_PREFIX + sha256(canonical.encode("utf-8")).hexdigest()


def _rejected(code: str, message: str) -> PlanPatchResult:
    error = patch_error(code, message=message)
    return PlanPatchResult(
        plan=None,
        result=PatchResult(
            status=PatchResultStatus.REJECTED,
            mutation_guarantee=error.mutation_guarantee,
            error=error,
        ),
    )


__all__ = ["PatchPlanningSnapshot", "PlanPatch", "PlanPatchResult"]
