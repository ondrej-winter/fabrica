"""Tests for deterministic apply-patch hunk matching."""

from fabrica.features.workspace_editing.application.dtos import (
    PatchHunk,
    PatchHunkLine,
    PatchHunkLineKind,
    PatchMatchQuality,
    PatchMutationGuarantee,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.text_snapshot import decode_patch_text
from fabrica.features.workspace_editing.application.use_cases import MatchHunks


def test_match_hunks_applies_exact_replacement_without_rewriting_context() -> None:
    snapshot = decode_patch_text(b"def value():\n    return 41\n")
    hunk = PatchHunk(
        index=1,
        lines=(
            PatchHunkLine(PatchHunkLineKind.CONTEXT, "def value():"),
            PatchHunkLine(PatchHunkLineKind.DELETE, "    return 41"),
            PatchHunkLine(PatchHunkLineKind.INSERT, "    return 42"),
        ),
    )

    matched = MatchHunks().match(snapshot, (hunk,))

    assert matched.result.status is PatchResultStatus.COMMITTED
    assert matched.lines == ("def value():", "    return 42")
    assert matched.match_quality is PatchMatchQuality.EXACT


def test_match_hunks_allows_trailing_whitespace_without_rewriting_context() -> None:
    snapshot = decode_patch_text(b"keep   \nold   \ntail\n")
    hunk = PatchHunk(
        index=1,
        lines=(
            PatchHunkLine(PatchHunkLineKind.CONTEXT, "keep"),
            PatchHunkLine(PatchHunkLineKind.DELETE, "old"),
            PatchHunkLine(PatchHunkLineKind.INSERT, "new"),
        ),
    )

    matched = MatchHunks().match(snapshot, (hunk,))

    assert matched.result.status is PatchResultStatus.COMMITTED
    assert matched.lines == ("keep   ", "new", "tail")
    assert matched.match_quality is PatchMatchQuality.TRAILING_WHITESPACE


def test_match_hunks_rejects_ambiguous_hunk_without_mutation() -> None:
    snapshot = decode_patch_text(b"target\ntarget\n")
    hunk = PatchHunk(index=1, lines=(PatchHunkLine(PatchHunkLineKind.DELETE, "target"),))

    matched = MatchHunks().match(snapshot, (hunk,))

    assert matched.lines == snapshot.lines
    assert matched.result.status is PatchResultStatus.REJECTED
    assert matched.result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION
    assert matched.result.error is not None
    assert matched.result.error.code == "AMBIGUOUS_HUNK"


def test_match_hunks_rejects_missing_and_ambiguous_anchors() -> None:
    hunk = PatchHunk(
        index=1,
        anchor="anchor",
        lines=(PatchHunkLine(PatchHunkLineKind.INSERT, "inserted"),),
        insert_relative_to_anchor="after",
    )

    missing = MatchHunks().match(decode_patch_text(b"other\n"), (hunk,))
    ambiguous = MatchHunks().match(decode_patch_text(b"anchor\nanchor\n"), (hunk,))

    assert missing.result.error is not None
    assert missing.result.error.code == "ANCHOR_NOT_FOUND"
    assert ambiguous.result.error is not None
    assert ambiguous.result.error.code == "AMBIGUOUS_ANCHOR"


def test_match_hunks_rejects_overlap_reverse_order_and_eof_failure() -> None:
    matcher = MatchHunks()
    first = PatchHunk(index=1, lines=(PatchHunkLine(PatchHunkLineKind.DELETE, "b"),))
    reversed_second = PatchHunk(index=2, lines=(PatchHunkLine(PatchHunkLineKind.DELETE, "a"),))
    overlapping_second = PatchHunk(index=2, lines=(PatchHunkLine(PatchHunkLineKind.CONTEXT, "b"),))
    eof_hunk = PatchHunk(index=1, lines=(PatchHunkLine(PatchHunkLineKind.DELETE, "a"),), assert_eof=True)

    reversed_result = matcher.match(decode_patch_text(b"a\nb\nc\n"), (first, reversed_second))
    overlap_result = matcher.match(decode_patch_text(b"a\nb\nc\n"), (first, overlapping_second))
    eof_result = matcher.match(decode_patch_text(b"a\nb\n"), (eof_hunk,))

    assert reversed_result.result.error is not None
    assert reversed_result.result.error.code == "HUNK_ORDER_CONFLICT"
    assert overlap_result.result.error is not None
    assert overlap_result.result.error.code == "HUNK_OVERLAP"
    assert eof_result.result.error is not None
    assert eof_result.result.error.code == "EOF_ASSERTION_FAILED"
