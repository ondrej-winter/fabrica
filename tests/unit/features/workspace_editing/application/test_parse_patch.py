"""Tests for the side-effect-free apply-patch parser."""

import pytest

from fabrica.features.workspace_editing.application.dtos import (
    PatchActionKind,
    PatchHunkLineKind,
    PatchLimits,
    PatchMutationGuarantee,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.use_cases import ParsePatch


def test_parse_patch_accepts_add_update_delete_and_move_actions() -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Add File: src/new.py\n"
        "+value = 42\n"
        "*** Update File: src/existing.py\n"
        "@@ def value():\n"
        " def value():\n"
        "-    return 41\n"
        "+    return 42\n"
        "*** End of File\n"
        "*** Update File: src/old.py\n"
        "*** Move to: src/renamed.py\n"
        "@@ after __all__ = []\n"
        "+EXPORTED = True\n"
        "*** Delete File: src/obsolete.py\n"
        "*** End Patch"
    )

    parsed = ParsePatch().parse(patch)

    assert parsed.plan is not None
    assert parsed.result.status is PatchResultStatus.COMMITTED
    assert parsed.result.mutation_guarantee is PatchMutationGuarantee.COMMITTED
    assert [action.kind for action in parsed.plan.actions] == [
        PatchActionKind.ADD,
        PatchActionKind.UPDATE,
        PatchActionKind.MOVE,
        PatchActionKind.DELETE,
    ]
    assert parsed.plan.actions[0].added_lines == ("value = 42",)
    assert parsed.plan.actions[1].hunks[0].anchor == "def value():"
    assert parsed.plan.actions[1].hunks[0].assert_eof is True
    assert parsed.plan.actions[1].hunks[0].lines[1].kind is PatchHunkLineKind.DELETE
    assert parsed.plan.actions[2].destination_path == "src/renamed.py"
    assert parsed.plan.actions[2].hunks[0].insert_relative_to_anchor == "after"
    assert parsed.result.plan_digest == parsed.plan.plan_digest


@pytest.mark.parametrize(
    ("patch", "expected_code"),
    [
        ("*** Add File: src/new.py\n+x\n*** End Patch", "INCOMPLETE_SENTINELS"),
        ("*** Begin Patch\n*** Touch File: src/new.py\n*** End Patch", "UNKNOWN_ACTION"),
        ("*** Begin Patch\n*** Add File: src/new.py\nplain\n*** End Patch", "INVALID_HUNK"),
        ("*** Begin Patch\n*** Delete File: src/obsolete.py\n-contents\n*** End Patch", "INVALID_PATCH"),
        ("*** Begin Patch\n*** Update File: src/existing.py\n*** End Patch", "NO_OP_ACTION"),
        ("*** Begin Patch\n\n*** End Patch", "INVALID_PATCH"),
        ("*** Begin Patch\n*** Update File: src/existing.py\nplain\n*** End Patch", "INVALID_HUNK"),
        (
            "*** Begin Patch\n*** Update File: src/existing.py\n*** Move to: src/existing.py\n*** End Patch",
            "NO_OP_ACTION",
        ),
        ("*** Begin Patch\n*** Update File: src/existing.py\n@@ bad\n*** End Patch", "INVALID_HUNK"),
        ("*** Begin Patch\n*** Update File: src/existing.py\n@@@ bad\n-context\n*** End Patch", "INVALID_HUNK"),
        ("*** Begin Patch\n*** Update File: src/existing.py\n@@ \n-context\n*** End Patch", "INVALID_HUNK"),
        ("*** Begin Patch\n*** Update File: src/existing.py\n@@ before \n+insert\n*** End Patch", "INVALID_HUNK"),
        ("*** Begin Patch\n*** Update File: src/existing.py\n@@ after \n+insert\n*** End Patch", "INVALID_HUNK"),
        ("*** Begin Patch\n*** Update File: src/existing.py\n@@\n+unsafe insert\n*** End Patch", "INVALID_HUNK"),
        (
            "*** Begin Patch\n*** Update File: src/existing.py\n@@ before anchor\n context\n*** End Patch",
            "INVALID_HUNK",
        ),
        (
            (
                "*** Begin Patch\n*** Update File: src/existing.py\n@@\n-old\n"
                "*** No Newline at End of File\n+late\n*** End Patch"
            ),
            "INVALID_HUNK",
        ),
        (
            "*** Begin Patch\n*** Update File: src/existing.py\n@@\n-context\n*** End of File\n+late\n*** End Patch",
            "INVALID_HUNK",
        ),
    ],
)
def test_parse_patch_rejects_invalid_canonical_forms(patch: str, expected_code: str) -> None:
    parsed = ParsePatch().parse(patch)

    assert parsed.plan is None
    assert parsed.result.status is PatchResultStatus.REJECTED
    assert parsed.result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION
    assert parsed.result.error is not None
    assert parsed.result.error.code == expected_code


def test_parse_patch_rejects_input_over_limit_without_parsing() -> None:
    patch = "*** Begin Patch\n*** Delete File: src/obsolete.py\n*** End Patch"

    parsed = ParsePatch().parse(patch, PatchLimits(max_input_chars=10))

    assert parsed.plan is None
    assert parsed.result.error is not None
    assert parsed.result.error.code == "LIMIT_EXCEEDED"


def test_parse_patch_accepts_pure_rename_with_no_hunks() -> None:
    patch = "*** Begin Patch\n*** Update File: src/old.py\n*** Move to: src/new.py\n*** End Patch"

    parsed = ParsePatch().parse(patch)

    assert parsed.plan is not None
    assert parsed.plan.actions[0].kind is PatchActionKind.MOVE
    assert parsed.plan.actions[0].hunks == ()


def test_parse_patch_accepts_terminal_newline_marker_at_hunk_end() -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Update File: src/existing.py\n"
        "@@\n"
        "-old\n"
        "+new\n"
        "*** No Newline at End of File\n"
        "*** End Patch"
    )

    parsed = ParsePatch().parse(patch)

    assert parsed.result.status is PatchResultStatus.COMMITTED
