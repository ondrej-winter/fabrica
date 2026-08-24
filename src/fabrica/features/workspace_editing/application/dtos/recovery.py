"""Durable journal and recovery DTOs for apply-patch mutation safety."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from fabrica.features.workspace_editing.application.dtos.patch import (
    PatchDirectoryOutcome,
    PatchMutationGuarantee,
    PatchPathOutcome,
    PatchResultStatus,
    SafePatchMetadataValue,
)


class PatchJournalState(StrEnum):
    """Durable lifecycle states recorded around visible workspace effects."""

    PLANNED = "planned"
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    RECOVERY_REQUIRED = "recovery_required"


class PatchRecoveryAction(StrEnum):
    """Startup recovery decision for an incomplete apply-patch journal."""

    NO_ACTION = "no_action"
    ROLL_BACK_PREPARATION = "roll_back_preparation"
    ROLL_BACK_COMMIT = "roll_back_commit"
    REQUIRE_OPERATOR_RECOVERY = "require_operator_recovery"


class PatchRecoveryStatus(StrEnum):
    """Terminal recovery status for one interrupted journal."""

    CLEAN = "clean"
    ROLLED_BACK = "rolled_back"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True)
class PatchJournalTransition:
    """One legal durable journal state transition."""

    source: PatchJournalState
    destination: PatchJournalState


@dataclass(frozen=True, slots=True)
class PatchJournalRecord:
    """Application-safe summary of one durable apply-patch journal."""

    journal_digest: str
    plan_digest: str
    state: PatchJournalState
    created_directories: tuple[PatchDirectoryOutcome, ...] = field(default_factory=tuple)
    path_outcomes: tuple[PatchPathOutcome, ...] = field(default_factory=tuple)
    metadata: Mapping[str, SafePatchMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_directories", tuple(self.created_directories))
        object.__setattr__(self, "path_outcomes", tuple(self.path_outcomes))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PatchRecoveryDecision:
    """Decision made after inspecting durable journal state at startup."""

    action: PatchRecoveryAction
    status: PatchRecoveryStatus
    mutation_guarantee: PatchMutationGuarantee
    result_status: PatchResultStatus | None = None

    def __post_init__(self) -> None:
        if (
            self.status is PatchRecoveryStatus.CLEAN
            and self.mutation_guarantee is not PatchMutationGuarantee.NO_MUTATION
        ):
            msg = "clean recovery decisions must guarantee no mutation"
            raise ValueError(msg)
        if self.status is PatchRecoveryStatus.RECOVERY_REQUIRED and (
            self.mutation_guarantee is not PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION
        ):
            msg = "operator recovery decisions must report partial or uncertain mutation"
            raise ValueError(msg)


LEGAL_PATCH_JOURNAL_TRANSITIONS = frozenset(
    {
        PatchJournalTransition(PatchJournalState.PLANNED, PatchJournalState.PREPARING),
        PatchJournalTransition(PatchJournalState.PREPARING, PatchJournalState.PREPARED),
        PatchJournalTransition(PatchJournalState.PREPARING, PatchJournalState.ROLLING_BACK),
        PatchJournalTransition(PatchJournalState.PREPARED, PatchJournalState.COMMITTING),
        PatchJournalTransition(PatchJournalState.PREPARED, PatchJournalState.ROLLING_BACK),
        PatchJournalTransition(PatchJournalState.COMMITTING, PatchJournalState.COMMITTED),
        PatchJournalTransition(PatchJournalState.COMMITTING, PatchJournalState.ROLLING_BACK),
        PatchJournalTransition(PatchJournalState.COMMITTING, PatchJournalState.RECOVERY_REQUIRED),
        PatchJournalTransition(PatchJournalState.ROLLING_BACK, PatchJournalState.ROLLED_BACK),
        PatchJournalTransition(PatchJournalState.ROLLING_BACK, PatchJournalState.RECOVERY_REQUIRED),
    }
)


RECOVERY_ACTION_BY_INTERRUPTED_STATE: Mapping[PatchJournalState, PatchRecoveryAction] = MappingProxyType(
    {
        PatchJournalState.PLANNED: PatchRecoveryAction.NO_ACTION,
        PatchJournalState.PREPARING: PatchRecoveryAction.ROLL_BACK_PREPARATION,
        PatchJournalState.PREPARED: PatchRecoveryAction.ROLL_BACK_PREPARATION,
        PatchJournalState.COMMITTING: PatchRecoveryAction.ROLL_BACK_COMMIT,
        PatchJournalState.ROLLING_BACK: PatchRecoveryAction.ROLL_BACK_COMMIT,
        PatchJournalState.RECOVERY_REQUIRED: PatchRecoveryAction.REQUIRE_OPERATOR_RECOVERY,
    }
)


TERMINAL_PATCH_JOURNAL_STATES = frozenset(
    {PatchJournalState.COMMITTED, PatchJournalState.ROLLED_BACK, PatchJournalState.RECOVERY_REQUIRED}
)


def is_legal_patch_journal_transition(source: PatchJournalState, destination: PatchJournalState) -> bool:
    """Return whether a durable journal transition is valid for v1 recovery."""
    return PatchJournalTransition(source, destination) in LEGAL_PATCH_JOURNAL_TRANSITIONS


__all__ = [
    "LEGAL_PATCH_JOURNAL_TRANSITIONS",
    "RECOVERY_ACTION_BY_INTERRUPTED_STATE",
    "TERMINAL_PATCH_JOURNAL_STATES",
    "PatchJournalRecord",
    "PatchJournalState",
    "PatchJournalTransition",
    "PatchRecoveryAction",
    "PatchRecoveryDecision",
    "PatchRecoveryStatus",
    "is_legal_patch_journal_transition",
]
