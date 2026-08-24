"""Exhaustive v1 apply-patch error table."""

from collections.abc import Mapping

from fabrica.features.workspace_editing.application.dtos import (
    PatchError,
    PatchErrorPhase,
    PatchMutationGuarantee,
    PatchRuntimeMapping,
    SafePatchMetadataValue,
)

type RequiredMetadata = tuple[str, ...]


def _error(
    code: str,
    phase: PatchErrorPhase,
    *,
    retryable: bool,
    mutation_guarantee: PatchMutationGuarantee = PatchMutationGuarantee.NO_MUTATION,
    runtime_mapping: PatchRuntimeMapping = PatchRuntimeMapping.REJECTED,
) -> PatchError:
    return PatchError(
        code=code,
        phase=phase,
        retryable=retryable,
        mutation_guarantee=mutation_guarantee,
        runtime_mapping=runtime_mapping,
    )


ERROR_TABLE: Mapping[str, PatchError] = {
    "INVALID_PATCH": _error("INVALID_PATCH", PatchErrorPhase.PARSING, retryable=True),
    "INCOMPLETE_SENTINELS": _error("INCOMPLETE_SENTINELS", PatchErrorPhase.PARSING, retryable=True),
    "UNKNOWN_ACTION": _error("UNKNOWN_ACTION", PatchErrorPhase.PARSING, retryable=True),
    "INVALID_HUNK": _error("INVALID_HUNK", PatchErrorPhase.PARSING, retryable=True),
    "NO_OP_ACTION": _error("NO_OP_ACTION", PatchErrorPhase.PLANNING, retryable=True),
    "DUPLICATE_ACTION": _error("DUPLICATE_ACTION", PatchErrorPhase.PLANNING, retryable=True),
    "PATH_ALIAS_COLLISION": _error("PATH_ALIAS_COLLISION", PatchErrorPhase.PLANNING, retryable=True),
    "SOURCE_NOT_FOUND": _error("SOURCE_NOT_FOUND", PatchErrorPhase.SNAPSHOT, retryable=True),
    "ADD_TARGET_EXISTS": _error("ADD_TARGET_EXISTS", PatchErrorPhase.SNAPSHOT, retryable=True),
    "MOVE_TARGET_EXISTS": _error("MOVE_TARGET_EXISTS", PatchErrorPhase.SNAPSHOT, retryable=True),
    "DESTINATION_COLLISION": _error("DESTINATION_COLLISION", PatchErrorPhase.PLANNING, retryable=True),
    "PATH_OUTSIDE_WORKSPACE": _error("PATH_OUTSIDE_WORKSPACE", PatchErrorPhase.PLANNING, retryable=True),
    "PROTECTED_PATH_DENIED": _error("PROTECTED_PATH_DENIED", PatchErrorPhase.POLICY, retryable=False),
    "SYMLINK_PATH_UNSUPPORTED": _error("SYMLINK_PATH_UNSUPPORTED", PatchErrorPhase.SNAPSHOT, retryable=False),
    "NOT_A_REGULAR_FILE": _error("NOT_A_REGULAR_FILE", PatchErrorPhase.SNAPSHOT, retryable=True),
    "PARENT_PATH_NOT_DIRECTORY": _error("PARENT_PATH_NOT_DIRECTORY", PatchErrorPhase.SNAPSHOT, retryable=True),
    "SPECIAL_FILE_UNSUPPORTED": _error("SPECIAL_FILE_UNSUPPORTED", PatchErrorPhase.SNAPSHOT, retryable=False),
    "MULTIPLE_HARD_LINKS_UNSUPPORTED": _error(
        "MULTIPLE_HARD_LINKS_UNSUPPORTED", PatchErrorPhase.SNAPSHOT, retryable=False
    ),
    "DIRECTORY_CREATION_UNSAFE": _error("DIRECTORY_CREATION_UNSAFE", PatchErrorPhase.PLANNING, retryable=True),
    "CREATED_DIRECTORY_RETAINED": _error(
        "CREATED_DIRECTORY_RETAINED",
        PatchErrorPhase.CLEANUP,
        retryable=False,
        mutation_guarantee=PatchMutationGuarantee.REVERSIBLE_EFFECTS_RETAINED,
        runtime_mapping=PatchRuntimeMapping.FATAL,
    ),
    "CREATED_DIRECTORY_REMOVAL_UNCERTAIN": _error(
        "CREATED_DIRECTORY_REMOVAL_UNCERTAIN",
        PatchErrorPhase.CLEANUP,
        retryable=False,
        mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
        runtime_mapping=PatchRuntimeMapping.FATAL,
    ),
    "CROSS_DEVICE_MOVE_UNSUPPORTED": _error(
        "CROSS_DEVICE_MOVE_UNSUPPORTED", PatchErrorPhase.CAPABILITY, retryable=False
    ),
    "UNSUPPORTED_FILESYSTEM_GUARANTEE": _error(
        "UNSUPPORTED_FILESYSTEM_GUARANTEE", PatchErrorPhase.CAPABILITY, retryable=False
    ),
    "BINARY_FILE": _error("BINARY_FILE", PatchErrorPhase.DECODING, retryable=True),
    "UNSUPPORTED_ENCODING": _error("UNSUPPORTED_ENCODING", PatchErrorPhase.DECODING, retryable=True),
    "MIXED_LINE_ENDINGS_UNSUPPORTED": _error(
        "MIXED_LINE_ENDINGS_UNSUPPORTED", PatchErrorPhase.DECODING, retryable=True
    ),
    "UNSUPPORTED_METADATA": _error("UNSUPPORTED_METADATA", PatchErrorPhase.SNAPSHOT, retryable=False),
    "ANCHOR_NOT_FOUND": _error("ANCHOR_NOT_FOUND", PatchErrorPhase.MATCHING, retryable=True),
    "AMBIGUOUS_ANCHOR": _error("AMBIGUOUS_ANCHOR", PatchErrorPhase.MATCHING, retryable=True),
    "HUNK_CONTEXT_NOT_FOUND": _error("HUNK_CONTEXT_NOT_FOUND", PatchErrorPhase.MATCHING, retryable=True),
    "AMBIGUOUS_HUNK": _error("AMBIGUOUS_HUNK", PatchErrorPhase.MATCHING, retryable=True),
    "HUNK_OVERLAP": _error("HUNK_OVERLAP", PatchErrorPhase.MATCHING, retryable=True),
    "HUNK_ORDER_CONFLICT": _error("HUNK_ORDER_CONFLICT", PatchErrorPhase.MATCHING, retryable=True),
    "EOF_ASSERTION_FAILED": _error("EOF_ASSERTION_FAILED", PatchErrorPhase.MATCHING, retryable=True),
    "LIMIT_EXCEEDED": _error("LIMIT_EXCEEDED", PatchErrorPhase.PLANNING, retryable=True),
    "APPROVAL_DENIED": _error("APPROVAL_DENIED", PatchErrorPhase.APPROVAL, retryable=True),
    "APPROVAL_TIMEOUT": _error("APPROVAL_TIMEOUT", PatchErrorPhase.APPROVAL, retryable=True),
    "STALE_PLAN": _error("STALE_PLAN", PatchErrorPhase.PREPARATION, retryable=True),
    "IO_ERROR": _error(
        "IO_ERROR", PatchErrorPhase.SNAPSHOT, retryable=True, runtime_mapping=PatchRuntimeMapping.ADAPTER_ERROR
    ),
    "PLANNING_TIMEOUT": _error(
        "PLANNING_TIMEOUT", PatchErrorPhase.PLANNING, retryable=True, runtime_mapping=PatchRuntimeMapping.TOOL_FAILURE
    ),
    "STAGING_TIMEOUT": _error(
        "STAGING_TIMEOUT", PatchErrorPhase.STAGING, retryable=False, runtime_mapping=PatchRuntimeMapping.TOOL_FAILURE
    ),
    "COMMIT_FAILED_ROLLED_BACK": _error(
        "COMMIT_FAILED_ROLLED_BACK",
        PatchErrorPhase.ROLLBACK,
        retryable=False,
        runtime_mapping=PatchRuntimeMapping.TOOL_FAILURE,
    ),
    "PARTIAL_COMMIT": _error(
        "PARTIAL_COMMIT",
        PatchErrorPhase.COMMIT,
        retryable=False,
        mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
        runtime_mapping=PatchRuntimeMapping.FATAL,
    ),
    "ROLLBACK_FAILED": _error(
        "ROLLBACK_FAILED",
        PatchErrorPhase.ROLLBACK,
        retryable=False,
        mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
        runtime_mapping=PatchRuntimeMapping.FATAL,
    ),
    "INDETERMINATE_COMMIT_STATE": _error(
        "INDETERMINATE_COMMIT_STATE",
        PatchErrorPhase.COMMIT,
        retryable=False,
        mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
        runtime_mapping=PatchRuntimeMapping.FATAL,
    ),
    "RECOVERY_REQUIRED": _error(
        "RECOVERY_REQUIRED",
        PatchErrorPhase.RECOVERY,
        retryable=False,
        mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
        runtime_mapping=PatchRuntimeMapping.FATAL,
    ),
}

REQUIRED_ERROR_METADATA: Mapping[str, RequiredMetadata] = {
    "HUNK_CONTEXT_NOT_FOUND": ("path", "hunk", "old_sequence_digest", "candidate_count"),
    "ANCHOR_NOT_FOUND": ("path", "hunk", "anchor"),
    "AMBIGUOUS_ANCHOR": ("path", "hunk", "anchor", "candidate_count"),
    "CREATED_DIRECTORY_RETAINED": ("path", "final_state"),
    "CREATED_DIRECTORY_REMOVAL_UNCERTAIN": ("path", "final_state"),
    "PARTIAL_COMMIT": ("plan_digest",),
    "ROLLBACK_FAILED": ("plan_digest",),
    "INDETERMINATE_COMMIT_STATE": ("plan_digest",),
    "RECOVERY_REQUIRED": ("journal_digest",),
}

EXPECTED_V1_ERROR_CODES = frozenset(ERROR_TABLE)


def patch_error(
    code: str,
    *,
    message: str | None = None,
    metadata: Mapping[str, SafePatchMetadataValue] | None = None,
) -> PatchError:
    """Return a concrete patch error from the exhaustive v1 table."""
    template = ERROR_TABLE[code]
    merged_metadata = dict(metadata or {})
    missing_metadata = set(REQUIRED_ERROR_METADATA.get(code, ())) - set(merged_metadata)
    if missing_metadata:
        msg = f"patch error {code} missing required metadata: {', '.join(sorted(missing_metadata))}"
        raise ValueError(msg)
    return PatchError(
        code=template.code,
        phase=template.phase,
        retryable=template.retryable,
        mutation_guarantee=template.mutation_guarantee,
        runtime_mapping=template.runtime_mapping,
        message=message,
        metadata=merged_metadata,
    )


__all__ = ["ERROR_TABLE", "EXPECTED_V1_ERROR_CODES", "REQUIRED_ERROR_METADATA", "patch_error"]
