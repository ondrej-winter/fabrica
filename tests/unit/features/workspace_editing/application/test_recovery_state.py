"""Tests for apply-patch journal and recovery state contracts."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.workspace_editing.application.dtos import (
    LEGAL_PATCH_JOURNAL_TRANSITIONS,
    RECOVERY_ACTION_BY_INTERRUPTED_STATE,
    TERMINAL_PATCH_JOURNAL_STATES,
    PatchJournalRecord,
    PatchJournalState,
    PatchJournalTransition,
    PatchMutationGuarantee,
    PatchRecoveryAction,
    PatchRecoveryDecision,
    PatchRecoveryStatus,
    WorkspaceMutationStartupGate,
    is_legal_patch_journal_transition,
)
from fabrica.features.workspace_editing.application.errors import patch_error

SHA256_A = "sha256:" + "a" * 64
SHA256_B = "sha256:" + "b" * 64


def test_journal_states_cover_legal_mutation_lifecycle_transitions() -> None:
    assert (
        frozenset(
            {
                PatchJournalTransition(PatchJournalState.PLANNED, PatchJournalState.PREPARING),
                PatchJournalTransition(PatchJournalState.PLANNED, PatchJournalState.ROLLED_BACK),
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
        == LEGAL_PATCH_JOURNAL_TRANSITIONS
    )
    assert is_legal_patch_journal_transition(PatchJournalState.PLANNED, PatchJournalState.PREPARING)
    assert not is_legal_patch_journal_transition(PatchJournalState.PLANNED, PatchJournalState.COMMITTED)


def test_recovery_actions_are_defined_for_every_incomplete_nonterminal_state() -> None:
    recoverable_states = set(PatchJournalState) - TERMINAL_PATCH_JOURNAL_STATES

    assert set(RECOVERY_ACTION_BY_INTERRUPTED_STATE) == recoverable_states | {PatchJournalState.RECOVERY_REQUIRED}
    assert RECOVERY_ACTION_BY_INTERRUPTED_STATE[PatchJournalState.PLANNED] is PatchRecoveryAction.NO_ACTION
    assert RECOVERY_ACTION_BY_INTERRUPTED_STATE[PatchJournalState.PREPARED] is PatchRecoveryAction.ROLL_BACK_PREPARATION
    assert RECOVERY_ACTION_BY_INTERRUPTED_STATE[PatchJournalState.COMMITTING] is PatchRecoveryAction.ROLL_BACK_COMMIT
    assert (
        RECOVERY_ACTION_BY_INTERRUPTED_STATE[PatchJournalState.RECOVERY_REQUIRED]
        is PatchRecoveryAction.REQUIRE_OPERATOR_RECOVERY
    )


def test_journal_records_are_immutable_and_copy_metadata() -> None:
    metadata = {"workspace": "primary"}

    record = PatchJournalRecord(
        journal_digest=SHA256_A,
        plan_digest=SHA256_B,
        state=PatchJournalState.PREPARING,
        metadata=metadata,
    )
    metadata["workspace"] = "changed"

    assert record.metadata["workspace"] == "primary"
    with pytest.raises(TypeError):
        cast("dict[str, object]", record.metadata)["workspace"] = "changed"
    frozen_field = "state"
    with pytest.raises(FrozenInstanceError):
        setattr(record, frozen_field, PatchJournalState.COMMITTED)


def test_recovery_decision_invariants_match_mutation_guarantees() -> None:
    PatchRecoveryDecision(
        action=PatchRecoveryAction.NO_ACTION,
        status=PatchRecoveryStatus.CLEAN,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
    )
    PatchRecoveryDecision(
        action=PatchRecoveryAction.REQUIRE_OPERATOR_RECOVERY,
        status=PatchRecoveryStatus.RECOVERY_REQUIRED,
        mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
    )

    with pytest.raises(ValueError, match="clean recovery"):
        PatchRecoveryDecision(
            action=PatchRecoveryAction.NO_ACTION,
            status=PatchRecoveryStatus.CLEAN,
            mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        )
    with pytest.raises(ValueError, match="operator recovery"):
        PatchRecoveryDecision(
            action=PatchRecoveryAction.REQUIRE_OPERATOR_RECOVERY,
            status=PatchRecoveryStatus.RECOVERY_REQUIRED,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        )


def test_workspace_mutation_startup_gate_requires_error_evidence_when_disabled() -> None:
    enabled = WorkspaceMutationStartupGate(mutation_enabled=True, recovered_journal_digests=(SHA256_A,))

    assert enabled.mutation_enabled
    assert enabled.recovered_journal_digests == (SHA256_A,)

    with pytest.raises(ValueError, match="disabled workspace"):
        WorkspaceMutationStartupGate(mutation_enabled=False)
    with pytest.raises(ValueError, match="enabled workspace"):
        WorkspaceMutationStartupGate(
            mutation_enabled=True,
            error=patch_error("UNSUPPORTED_FILESYSTEM_GUARANTEE", message="unexpected"),
        )
