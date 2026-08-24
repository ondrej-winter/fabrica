"""Tests for apply-patch application DTO contracts."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchChangeSummary,
    PatchDirectoryOutcome,
    PatchDirectoryOutcomeState,
    PatchDirectoryPlannedEffect,
    PatchError,
    PatchErrorPhase,
    PatchHunk,
    PatchLimits,
    PatchMatchQuality,
    PatchMutationGuarantee,
    PatchPathEvidence,
    PatchResult,
    PatchResultStatus,
    PatchRuntimeMapping,
)
from fabrica.features.workspace_editing.application.errors import (
    ERROR_TABLE,
    EXPECTED_V1_ERROR_CODES,
    REQUIRED_ERROR_METADATA,
    patch_error,
)

SHA256_A = "sha256:" + "a" * 64
SHA256_B = "sha256:" + "b" * 64
EXPECTED_HUNK_INDEX = 2


REQUIRED_SPEC_ERROR_CODES = {
    "INVALID_PATCH",
    "INCOMPLETE_SENTINELS",
    "UNKNOWN_ACTION",
    "INVALID_HUNK",
    "NO_OP_ACTION",
    "DUPLICATE_ACTION",
    "PATH_ALIAS_COLLISION",
    "SOURCE_NOT_FOUND",
    "ADD_TARGET_EXISTS",
    "MOVE_TARGET_EXISTS",
    "DESTINATION_COLLISION",
    "PATH_OUTSIDE_WORKSPACE",
    "PROTECTED_PATH_DENIED",
    "SYMLINK_PATH_UNSUPPORTED",
    "NOT_A_REGULAR_FILE",
    "PARENT_PATH_NOT_DIRECTORY",
    "SPECIAL_FILE_UNSUPPORTED",
    "MULTIPLE_HARD_LINKS_UNSUPPORTED",
    "DIRECTORY_CREATION_UNSAFE",
    "CREATED_DIRECTORY_RETAINED",
    "CREATED_DIRECTORY_REMOVAL_UNCERTAIN",
    "CROSS_DEVICE_MOVE_UNSUPPORTED",
    "UNSUPPORTED_FILESYSTEM_GUARANTEE",
    "BINARY_FILE",
    "UNSUPPORTED_ENCODING",
    "MIXED_LINE_ENDINGS_UNSUPPORTED",
    "UNSUPPORTED_METADATA",
    "ANCHOR_NOT_FOUND",
    "AMBIGUOUS_ANCHOR",
    "HUNK_CONTEXT_NOT_FOUND",
    "AMBIGUOUS_HUNK",
    "HUNK_OVERLAP",
    "HUNK_ORDER_CONFLICT",
    "EOF_ASSERTION_FAILED",
    "LIMIT_EXCEEDED",
    "APPROVAL_DENIED",
    "APPROVAL_TIMEOUT",
    "STALE_PLAN",
    "IO_ERROR",
    "PLANNING_TIMEOUT",
    "STAGING_TIMEOUT",
    "COMMIT_FAILED_ROLLED_BACK",
    "PARTIAL_COMMIT",
    "ROLLBACK_FAILED",
    "INDETERMINATE_COMMIT_STATE",
    "RECOVERY_REQUIRED",
}


def test_patch_status_and_guarantee_values_match_spec_contract() -> None:
    assert {status.value for status in PatchResultStatus} == {
        "committed",
        "rejected",
        "commit_failed_rolled_back",
        "partial_commit",
        "rollback_failed",
        "indeterminate_commit_state",
        "recovery_required",
    }
    assert {guarantee.value for guarantee in PatchMutationGuarantee} == {
        "no_mutation",
        "committed",
        "reversible_effects_retained",
        "partial_or_uncertain_mutation",
    }


def test_patch_dtos_are_immutable_and_copy_container_inputs() -> None:
    metadata = {"mode": "100644"}
    evidence = PatchPathEvidence(path="src/example.py", exists=True, content_digest=SHA256_A, metadata=metadata)
    metadata["mode"] = "changed"

    assert evidence.metadata["mode"] == "100644"
    with pytest.raises(TypeError):
        cast("dict[str, object]", evidence.metadata)["mode"] = "changed"

    result = PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=SHA256_A,
    )
    with pytest.raises(FrozenInstanceError):
        result.status = PatchResultStatus.REJECTED  # ty: ignore[invalid-assignment]


def test_patch_limits_and_paths_reject_invalid_inputs() -> None:
    assert PatchLimits(max_input_chars=1, max_output_chars=1).max_input_chars == 1
    with pytest.raises(ValueError, match="max_input_chars must be at least 1"):
        PatchLimits(max_input_chars=0)
    with pytest.raises(ValueError, match="max_output_chars must be at least 1"):
        PatchLimits(max_output_chars=0)
    with pytest.raises(ValueError, match="workspace-relative"):
        PatchAction(index=0, kind=PatchActionKind.ADD, path="../outside.py")
    with pytest.raises(ValueError, match="move actions must include"):
        PatchAction(index=0, kind=PatchActionKind.MOVE, path="src/example.py")
    with pytest.raises(ValueError, match="only move actions"):
        PatchAction(
            index=0,
            kind=PatchActionKind.UPDATE,
            path="src/example.py",
            destination_path="src/new_example.py",
        )


def test_patch_hunk_rejects_invalid_index_and_anchor_placement() -> None:
    with pytest.raises(ValueError, match="hunk index must be one-based"):
        PatchHunk(index=0)
    with pytest.raises(ValueError, match="insert_relative_to_anchor"):
        PatchHunk(index=1, insert_relative_to_anchor="around")


def test_error_table_is_exhaustive_and_contains_required_runtime_mapping() -> None:
    assert EXPECTED_V1_ERROR_CODES == REQUIRED_SPEC_ERROR_CODES
    assert set(ERROR_TABLE) == REQUIRED_SPEC_ERROR_CODES
    assert all(error.phase is not None for error in ERROR_TABLE.values())
    assert all(error.runtime_mapping is not PatchRuntimeMapping.SUCCESS for error in ERROR_TABLE.values())
    assert ERROR_TABLE["HUNK_CONTEXT_NOT_FOUND"].phase is PatchErrorPhase.MATCHING
    assert ERROR_TABLE["HUNK_CONTEXT_NOT_FOUND"].retryable is True
    assert ERROR_TABLE["ROLLBACK_FAILED"].runtime_mapping is PatchRuntimeMapping.FATAL
    assert ERROR_TABLE["ROLLBACK_FAILED"].mutation_guarantee is PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION


def test_patch_error_factory_enforces_required_metadata() -> None:
    with pytest.raises(ValueError, match="missing required metadata"):
        patch_error("HUNK_CONTEXT_NOT_FOUND", metadata={"path": "src/example.py"})

    error = patch_error(
        "HUNK_CONTEXT_NOT_FOUND",
        message="context not found",
        metadata={
            "path": "src/example.py",
            "hunk": EXPECTED_HUNK_INDEX,
            "old_sequence_digest": SHA256_A,
            "candidate_count": 0,
        },
    )

    assert error.code == "HUNK_CONTEXT_NOT_FOUND"
    assert error.metadata["hunk"] == EXPECTED_HUNK_INDEX
    assert REQUIRED_ERROR_METADATA["HUNK_CONTEXT_NOT_FOUND"] == (
        "path",
        "hunk",
        "old_sequence_digest",
        "candidate_count",
    )


def test_result_invariants_follow_success_and_error_contract() -> None:
    success = PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=SHA256_A,
    )
    rejection_error = patch_error("INVALID_PATCH")
    rejection = PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        error=rejection_error,
    )

    assert success.succeeded is True
    assert rejection.succeeded is False
    with pytest.raises(ValueError, match="committed results must carry"):
        PatchResult(status=PatchResultStatus.COMMITTED, mutation_guarantee=PatchMutationGuarantee.NO_MUTATION)
    with pytest.raises(ValueError, match="non-committed results must include an error"):
        PatchResult(status=PatchResultStatus.REJECTED, mutation_guarantee=PatchMutationGuarantee.NO_MUTATION)
    with pytest.raises(ValueError, match="must match the error table"):
        PatchResult(
            status=PatchResultStatus.REJECTED,
            mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
            error=rejection_error,
        )


def test_result_serialization_preserves_required_fields_when_bounded() -> None:
    error = patch_error(
        "HUNK_CONTEXT_NOT_FOUND",
        message="context not found",
        metadata={
            "path": "src/example.py",
            "hunk": EXPECTED_HUNK_INDEX,
            "anchor": None,
            "old_sequence_digest": SHA256_A,
            "candidate_count": 0,
            "excerpt": "x" * 500,
        },
    )
    result = PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        error=error,
    )

    serialized = result.to_bounded_json(max_chars=180)

    assert '"status":"rejected"' in serialized
    assert '"success":false' in serialized
    assert '"mutation_guarantee":"no_mutation"' in serialized
    assert '"code":"HUNK_CONTEXT_NOT_FOUND"' in serialized
    assert '"phase":"matching"' in serialized
    assert '"retryable":true' in serialized
    assert "excerpt" not in serialized
    with pytest.raises(ValueError, match="mandatory patch result fields"):
        result.to_bounded_json(max_chars=10)


def test_success_result_serialization_includes_changes_and_directory_effects() -> None:
    result = PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=SHA256_A,
        changes=(
            PatchChangeSummary(
                index=0,
                operation=PatchActionKind.UPDATE,
                path="src/example.py",
                hunks=2,
                match_quality=PatchMatchQuality.EXACT,
            ),
        ),
        created_directories=(
            PatchDirectoryOutcome(
                path="tests/generated",
                planned_effect=PatchDirectoryPlannedEffect.CREATE_DIRECTORY,
                final_state=PatchDirectoryOutcomeState.CREATED,
                reason="parent_for_add",
                identity_digest=SHA256_B,
            ),
        ),
        warnings=(),
    )

    serialized = result.to_bounded_json()

    assert '"plan_digest":"sha256:' in serialized
    assert '"operation":"update"' in serialized
    assert '"match_quality":"exact"' in serialized
    assert '"created_directories"' in serialized
    assert '"reason":"parent_for_add"' in serialized


def test_error_code_and_digest_validation_rejects_unsafe_values() -> None:
    with pytest.raises(ValueError, match="upper snake case"):
        PatchError(
            code="invalid-patch",
            phase=PatchErrorPhase.PARSING,
            retryable=True,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
            runtime_mapping=PatchRuntimeMapping.REJECTED,
        )
    with pytest.raises(ValueError, match="sha256 digest"):
        PatchResult(
            status=PatchResultStatus.COMMITTED,
            mutation_guarantee=PatchMutationGuarantee.COMMITTED,
            plan_digest="bad",
        )
