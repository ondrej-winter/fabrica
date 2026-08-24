"""Tests for pure immutable apply-patch planning."""

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchCommitOperation,
    PatchLimits,
    PatchMutationGuarantee,
    PatchPathEvidence,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.use_cases import PatchPlanningSnapshot, PlanPatch

SHA256_A = "sha256:" + "a" * 64
SHA256_B = "sha256:" + "b" * 64


def test_plan_patch_derives_collapsed_directory_effects_and_distinct_commit_order() -> None:
    actions = (
        PatchAction(index=0, kind=PatchActionKind.ADD, path="src/generated/a.py", added_lines=("A = 1",)),
        PatchAction(index=1, kind=PatchActionKind.ADD, path="src/generated/nested/b.py", added_lines=("B = 2",)),
        PatchAction(index=2, kind=PatchActionKind.DELETE, path="src/old.py"),
    )
    snapshot = PatchPlanningSnapshot(
        evidence_by_path={"src/old.py": PatchPathEvidence("src/old.py", exists=True, content_digest=SHA256_A)},
        existing_directories=frozenset({"", "src"}),
    )

    planned = PlanPatch().plan(actions, snapshot)

    assert planned.plan is not None
    assert planned.result.status is PatchResultStatus.COMMITTED
    assert [directory.path for directory in planned.plan.created_directories] == [
        "src/generated",
        "src/generated/nested",
    ]
    assert [step.operation for step in planned.plan.commit_steps] == [
        PatchCommitOperation.CREATE_DIRECTORY,
        PatchCommitOperation.CREATE_DIRECTORY,
        PatchCommitOperation.WRITE_FILE,
        PatchCommitOperation.WRITE_FILE,
        PatchCommitOperation.DELETE_FILE,
    ]
    assert [change.path for change in planned.plan.changes] == [
        "src/generated/a.py",
        "src/generated/nested/b.py",
        "src/old.py",
    ]
    assert planned.plan.approval_preview is not None
    assert "create directory src/generated" in planned.plan.approval_preview.text
    assert planned.result.created_directories == planned.plan.created_directories


def test_plan_patch_digest_binds_evidence_schedule_and_preview() -> None:
    action = PatchAction(index=0, kind=PatchActionKind.DELETE, path="src/old.py")
    first = PlanPatch().plan(
        (action,),
        PatchPlanningSnapshot(
            evidence_by_path={"src/old.py": PatchPathEvidence("src/old.py", exists=True, content_digest=SHA256_A)}
        ),
    )
    second = PlanPatch().plan(
        (action,),
        PatchPlanningSnapshot(
            evidence_by_path={"src/old.py": PatchPathEvidence("src/old.py", exists=True, content_digest=SHA256_B)}
        ),
    )

    assert first.plan is not None
    assert second.plan is not None
    assert first.plan.plan_digest != second.plan.plan_digest


def test_plan_patch_rejects_global_source_destination_collisions_without_mutation() -> None:
    actions = (
        PatchAction(index=0, kind=PatchActionKind.ADD, path="src/new.py"),
        PatchAction(index=1, kind=PatchActionKind.MOVE, path="src/old.py", destination_path="src/new.py"),
    )

    planned = PlanPatch().plan(actions, PatchPlanningSnapshot())

    assert planned.plan is None
    assert planned.result.status is PatchResultStatus.REJECTED
    assert planned.result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION
    assert planned.result.error is not None
    assert planned.result.error.code == "DESTINATION_COLLISION"


def test_plan_patch_rejects_unapprovable_truncated_preview() -> None:
    actions = (PatchAction(index=0, kind=PatchActionKind.ADD, path="src/new.py"),)

    planned = PlanPatch().plan(actions, PatchPlanningSnapshot(), PatchLimits(max_output_chars=10))

    assert planned.plan is None
    assert planned.result.error is not None
    assert planned.result.error.code == "LIMIT_EXCEEDED"
