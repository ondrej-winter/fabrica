"""Deterministic hunk matching against immutable text snapshots."""

from dataclasses import dataclass
from hashlib import sha256

from fabrica.features.workspace_editing.application.dtos import (
    PatchHunk,
    PatchHunkLineKind,
    PatchMatchQuality,
    PatchMutationGuarantee,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from fabrica.features.workspace_editing.application.text_snapshot import PatchTextSnapshot

PLAN_DIGEST_PREFIX = "sha256:"


@dataclass(frozen=True, slots=True)
class MatchHunksResult:
    """Result of matching and applying hunks without mutating the workspace."""

    lines: tuple[str, ...]
    result: PatchResult
    match_quality: PatchMatchQuality | None = None


@dataclass(frozen=True, slots=True)
class _Candidate:
    start: int
    end: int
    quality: PatchMatchQuality


@dataclass(frozen=True, slots=True)
class _MatchedHunk:
    candidate: _Candidate | None = None
    rejection: PatchResult | None = None

    def __post_init__(self) -> None:
        if (self.candidate is None) == (self.rejection is None):
            msg = "matched hunk must carry exactly one candidate or rejection"
            raise ValueError(msg)


class MatchHunks:
    """Match parsed update hunks against one immutable source snapshot."""

    def match(self, snapshot: PatchTextSnapshot, hunks: tuple[PatchHunk, ...]) -> MatchHunksResult:
        """Return replacement lines or a no-mutation structured rejection."""
        current_lines = list(snapshot.lines)
        matched_spans: list[tuple[int, int]] = []
        worst_quality = PatchMatchQuality.EXACT

        for hunk in hunks:
            matched_hunk = self._match_hunk(snapshot.lines, hunk)
            if matched_hunk.rejection is not None:
                return MatchHunksResult(lines=snapshot.lines, result=matched_hunk.rejection)
            candidate = matched_hunk.candidate
            if candidate is None:
                msg = "matched hunk unexpectedly omitted a candidate"
                raise RuntimeError(msg)
            if matched_spans and candidate.start < matched_spans[-1][0]:
                return _rejected("HUNK_ORDER_CONFLICT", hunk=hunk)
            if matched_spans and candidate.start < matched_spans[-1][1]:
                return _rejected("HUNK_OVERLAP", hunk=hunk)
            if hunk.assert_eof and candidate.end != len(snapshot.lines):
                return _rejected("EOF_ASSERTION_FAILED", hunk=hunk)

            offset = len(current_lines) - len(snapshot.lines)
            replacement = _replacement_lines(snapshot.lines, hunk, candidate)
            current_lines[candidate.start + offset : candidate.end + offset] = replacement
            matched_spans.append((candidate.start, candidate.end))
            if candidate.quality is PatchMatchQuality.TRAILING_WHITESPACE:
                worst_quality = PatchMatchQuality.TRAILING_WHITESPACE

        return MatchHunksResult(
            lines=tuple(current_lines),
            result=PatchResult(
                status=PatchResultStatus.COMMITTED,
                mutation_guarantee=PatchMutationGuarantee.COMMITTED,
                plan_digest=_digest_lines(tuple(current_lines)),
            ),
            match_quality=worst_quality if hunks else None,
        )

    def _match_hunk(self, source_lines: tuple[str, ...], hunk: PatchHunk) -> _MatchedHunk:
        anchored = _find_anchor(source_lines, hunk)
        if isinstance(anchored, PatchResult):
            return _MatchedHunk(rejection=anchored)

        placement_candidate = _placement_candidate(anchored, hunk.insert_relative_to_anchor)
        if placement_candidate is not None:
            return _MatchedHunk(candidate=placement_candidate)

        old_sequence = _old_sequence(hunk)
        search_start = 0 if anchored is None else anchored + 1
        candidate = _unique_sequence_candidate(source_lines, old_sequence, search_start, hunk)
        if isinstance(candidate, PatchResult):
            return _MatchedHunk(rejection=candidate)
        return _MatchedHunk(candidate=candidate)


def _find_sequence_matches(
    source_lines: tuple[str, ...],
    old_sequence: tuple[str, ...],
    search_start: int,
    quality: PatchMatchQuality,
) -> list[_Candidate]:
    matches: list[_Candidate] = []
    if not old_sequence:
        return matches
    for start in range(search_start, len(source_lines) - len(old_sequence) + 1):
        candidate_lines = source_lines[start : start + len(old_sequence)]
        if quality is PatchMatchQuality.EXACT:
            matched = candidate_lines == old_sequence
        else:
            matched = all(
                source.rstrip() == patch.rstrip() for source, patch in zip(candidate_lines, old_sequence, strict=True)
            )
        if matched:
            matches.append(_Candidate(start=start, end=start + len(old_sequence), quality=quality))
    return matches


def _find_anchor(source_lines: tuple[str, ...], hunk: PatchHunk) -> int | PatchResult | None:
    if hunk.anchor is None:
        return None
    anchor_matches = [index for index, line in enumerate(source_lines) if line == hunk.anchor]
    if not anchor_matches:
        return _rejected("ANCHOR_NOT_FOUND", hunk=hunk, anchor=hunk.anchor).result
    if len(anchor_matches) > 1:
        return _rejected(
            "AMBIGUOUS_ANCHOR",
            hunk=hunk,
            anchor=hunk.anchor,
            candidate_count=len(anchor_matches),
        ).result
    return anchor_matches[0]


def _placement_candidate(anchor_index: int | None, placement: str | None) -> _Candidate | None:
    if placement == "before":
        start = anchor_index or 0
        return _Candidate(start=start, end=start, quality=PatchMatchQuality.EXACT)
    if placement == "after":
        start = (anchor_index or 0) + 1
        return _Candidate(start=start, end=start, quality=PatchMatchQuality.EXACT)
    return None


def _unique_sequence_candidate(
    source_lines: tuple[str, ...],
    old_sequence: tuple[str, ...],
    search_start: int,
    hunk: PatchHunk,
) -> _Candidate | PatchResult:
    exact_matches = _find_sequence_matches(source_lines, old_sequence, search_start, PatchMatchQuality.EXACT)
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return _rejected("AMBIGUOUS_HUNK", hunk=hunk, candidate_count=len(exact_matches)).result

    whitespace_matches = _find_sequence_matches(
        source_lines,
        old_sequence,
        search_start,
        PatchMatchQuality.TRAILING_WHITESPACE,
    )
    if len(whitespace_matches) == 1:
        return whitespace_matches[0]
    if len(whitespace_matches) > 1:
        return _rejected("AMBIGUOUS_HUNK", hunk=hunk, candidate_count=len(whitespace_matches)).result
    return _rejected("HUNK_CONTEXT_NOT_FOUND", hunk=hunk, candidate_count=0).result


def _replacement_lines(source_lines: tuple[str, ...], hunk: PatchHunk, candidate: _Candidate) -> list[str]:
    replacement: list[str] = []
    source_index = candidate.start
    for line in hunk.lines:
        if line.kind is PatchHunkLineKind.INSERT:
            replacement.append(line.text)
        elif line.kind is PatchHunkLineKind.CONTEXT:
            replacement.append(source_lines[source_index])
            source_index += 1
        else:
            source_index += 1
    return replacement


def _rejected(code: str, *, hunk: PatchHunk, anchor: str | None = None, candidate_count: int = 0) -> MatchHunksResult:
    old_sequence = _old_sequence(hunk)
    metadata = {
        "path": "<pending-plan>",
        "hunk": hunk.index,
        "old_sequence_digest": _digest_lines(old_sequence),
        "candidate_count": candidate_count,
    }
    if anchor is not None:
        metadata["anchor"] = anchor
    return MatchHunksResult(
        lines=(),
        result=PatchResult(
            status=PatchResultStatus.REJECTED,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
            error=patch_error(code, metadata=metadata),
        ),
    )


def _old_sequence(hunk: PatchHunk) -> tuple[str, ...]:
    return tuple(line.text for line in hunk.lines if line.kind is not PatchHunkLineKind.INSERT)


def _digest_lines(lines: tuple[str, ...]) -> str:
    return PLAN_DIGEST_PREFIX + sha256("\n".join(lines).encode("utf-8")).hexdigest()


__all__ = ["MatchHunks", "MatchHunksResult"]
