"""Side-effect-free parser for the canonical apply-patch protocol."""

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Never

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchActionKind,
    PatchChangeSummary,
    PatchHunk,
    PatchHunkLine,
    PatchHunkLineKind,
    PatchLimits,
    PatchMutationGuarantee,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error

BEGIN_SENTINEL = "*** Begin Patch"
END_SENTINEL = "*** End Patch"
ADD_HEADER = "*** Add File: "
UPDATE_HEADER = "*** Update File: "
DELETE_HEADER = "*** Delete File: "
MOVE_HEADER = "*** Move to: "
HUNK_HEADER = "@@"
EOF_ASSERTION = "*** End of File"
NO_NEWLINE_MARKER = "*** No Newline at End of File"
PLAN_DIGEST_PREFIX = "sha256:"


@dataclass(frozen=True, slots=True)
class ParsePatchResult:
    """Result of parsing a patch without touching workspace state."""

    plan: PatchPlan | None
    result: PatchResult


class ParsePatch:
    """Parse canonical apply-patch text into immutable application DTOs."""

    def parse(self, patch_text: str, limits: PatchLimits | None = None) -> ParsePatchResult:
        """Parse one canonical patch body without reading or mutating files."""
        active_limits = limits or PatchLimits()
        if len(patch_text) > active_limits.max_input_chars:
            return _rejected("LIMIT_EXCEEDED", "patch input exceeds the configured character limit")

        lines = patch_text.splitlines()
        if not lines or lines[0] != BEGIN_SENTINEL or lines[-1] != END_SENTINEL:
            return _rejected("INCOMPLETE_SENTINELS", "patch must start and end with canonical sentinels")

        parser = _PatchParser(lines[1:-1], original_text=patch_text)
        try:
            return parser.parse()
        except _ParseRejectionError as err:
            return _rejected(err.code, err.message)


class _PatchParser:
    def __init__(self, body_lines: Sequence[str], *, original_text: str) -> None:
        self._body_lines = tuple(body_lines)
        self._original_text = original_text
        self._position = 0
        self._actions: list[PatchAction] = []

    def parse(self) -> ParsePatchResult:
        while self._position < len(self._body_lines):
            line = self._body_lines[self._position]
            if line.startswith(ADD_HEADER):
                self._actions.append(self._parse_add())
            elif line.startswith(UPDATE_HEADER):
                self._actions.append(self._parse_update_or_move())
            elif line.startswith(DELETE_HEADER):
                self._actions.append(self._parse_delete())
            elif line == "":
                return _rejected("INVALID_PATCH", "empty lines are not valid action headers")
            else:
                return _rejected("UNKNOWN_ACTION", "patch body contains an unknown action header")

        if not self._actions:
            return _rejected("INVALID_PATCH", "patch must include at least one action")
        plan = PatchPlan(
            plan_digest=_digest(self._original_text),
            actions=tuple(self._actions),
            changes=tuple(_change_summary(action) for action in self._actions),
        )
        return ParsePatchResult(
            plan=plan,
            result=PatchResult(
                status=PatchResultStatus.COMMITTED,
                mutation_guarantee=PatchMutationGuarantee.COMMITTED,
                plan_digest=plan.plan_digest,
                changes=plan.changes,
            ),
        )

    def _parse_add(self) -> PatchAction:
        header = self._consume()
        added_lines: list[str] = []
        while self._position < len(self._body_lines) and not _is_action_header(self._body_lines[self._position]):
            line = self._consume()
            if not line.startswith("+"):
                _reject_parse("INVALID_HUNK", "add file content lines must start with +")
            added_lines.append(line[1:])
        return PatchAction(
            index=len(self._actions),
            kind=PatchActionKind.ADD,
            path=header.removeprefix(ADD_HEADER),
            added_lines=tuple(added_lines),
        )

    def _parse_delete(self) -> PatchAction:
        header = self._consume()
        if self._position < len(self._body_lines) and not _is_action_header(self._body_lines[self._position]):
            _reject_parse("INVALID_PATCH", "delete file actions must not include body lines")
        return PatchAction(
            index=len(self._actions), kind=PatchActionKind.DELETE, path=header.removeprefix(DELETE_HEADER)
        )

    def _parse_update_or_move(self) -> PatchAction:
        header = self._consume()
        destination_path = self._consume_move_destination_if_present()
        hunks: list[PatchHunk] = []
        while self._position < len(self._body_lines) and not _is_action_header(self._body_lines[self._position]):
            if not self._body_lines[self._position].startswith(HUNK_HEADER):
                _reject_parse("INVALID_HUNK", "update body lines must follow a hunk header")
            hunks.append(self._parse_hunk(index=len(hunks) + 1))

        kind = PatchActionKind.MOVE if destination_path is not None else PatchActionKind.UPDATE
        action = PatchAction(
            index=len(self._actions),
            kind=kind,
            path=header.removeprefix(UPDATE_HEADER),
            destination_path=destination_path,
            hunks=tuple(hunks),
        )
        if kind is PatchActionKind.UPDATE and not _hunks_change_content(hunks):
            _reject_parse("NO_OP_ACTION", "update actions must contain an effective hunk")
        if kind is PatchActionKind.MOVE and destination_path == action.path:
            _reject_parse("NO_OP_ACTION", "move destination must differ from the source path")
        return action

    def _consume_move_destination_if_present(self) -> str | None:
        if self._position >= len(self._body_lines) or not self._body_lines[self._position].startswith(MOVE_HEADER):
            return None
        return self._consume().removeprefix(MOVE_HEADER)

    def _parse_hunk(self, *, index: int) -> PatchHunk:
        header = self._consume()
        anchor, insert_relative_to_anchor = _parse_hunk_header(header)
        lines: list[PatchHunkLine] = []
        assert_eof = False

        while self._position < len(self._body_lines):
            line = self._body_lines[self._position]
            if _is_action_header(line) or line.startswith(HUNK_HEADER):
                break
            line = self._consume()
            if line == EOF_ASSERTION:
                if self._position < len(self._body_lines) and not _is_action_header(self._body_lines[self._position]):
                    _reject_parse("INVALID_HUNK", "EOF assertion must be the final line of the final hunk")
                assert_eof = True
                break
            if line == NO_NEWLINE_MARKER:
                if self._position < len(self._body_lines) and not _is_action_header_or_hunk(
                    self._body_lines[self._position]
                ):
                    _reject_parse("INVALID_HUNK", "terminal-newline marker may appear only at the end of a hunk")
                continue
            lines.append(_parse_hunk_line(line))

        if not lines:
            _reject_parse("INVALID_HUNK", "hunks must contain at least one tagged content line")
        if insert_relative_to_anchor is not None and any(line.kind is not PatchHunkLineKind.INSERT for line in lines):
            _reject_parse("INVALID_HUNK", "before/after hunks may contain inserted lines only")
        if insert_relative_to_anchor is None and all(line.kind is PatchHunkLineKind.INSERT for line in lines):
            _reject_parse("INVALID_HUNK", "insertion-only hunks require before or after placement")
        return PatchHunk(
            index=index,
            lines=tuple(lines),
            anchor=anchor,
            insert_relative_to_anchor=insert_relative_to_anchor,
            assert_eof=assert_eof,
        )

    def _consume(self) -> str:
        line = self._body_lines[self._position]
        self._position += 1
        return line


class _ParseRejectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _rejected(code: str, message: str) -> ParsePatchResult:
    return ParsePatchResult(
        plan=None,
        result=PatchResult(
            status=PatchResultStatus.REJECTED,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
            error=patch_error(code, message=message),
        ),
    )


def _is_action_header(line: str) -> bool:
    return line.startswith((ADD_HEADER, UPDATE_HEADER, DELETE_HEADER))


def _is_action_header_or_hunk(line: str) -> bool:
    return _is_action_header(line) or line.startswith(HUNK_HEADER)


def _parse_hunk_header(header: str) -> tuple[str | None, str | None]:
    if header == HUNK_HEADER:
        return None, None
    if not header.startswith("@@ "):
        _reject_parse("INVALID_HUNK", "hunk headers must be @@, @@ <anchor>, @@ before <anchor>, or @@ after <anchor>")
    anchor = header.removeprefix("@@ ")
    if not anchor:
        _reject_parse("INVALID_HUNK", "hunk anchors must not be empty")
    if anchor.startswith("before "):
        placement_anchor = anchor.removeprefix("before ")
        if not placement_anchor:
            _reject_parse("INVALID_HUNK", "before placement requires an anchor")
        return placement_anchor, "before"
    if anchor.startswith("after "):
        placement_anchor = anchor.removeprefix("after ")
        if not placement_anchor:
            _reject_parse("INVALID_HUNK", "after placement requires an anchor")
        return placement_anchor, "after"
    return anchor, None


def _parse_hunk_line(line: str) -> PatchHunkLine:
    if not line:
        _reject_parse("INVALID_HUNK", "hunk body lines must be tagged")
    prefix = line[0]
    if prefix == " ":
        return PatchHunkLine(kind=PatchHunkLineKind.CONTEXT, text=line[1:])
    if prefix == "-":
        return PatchHunkLine(kind=PatchHunkLineKind.DELETE, text=line[1:])
    if prefix == "+":
        return PatchHunkLine(kind=PatchHunkLineKind.INSERT, text=line[1:])
    return _reject_parse("INVALID_HUNK", "hunk body lines must start with space, -, or +")


def _reject_parse(code: str, message: str) -> Never:
    raise _ParseRejectionError(code, message)


def _hunks_change_content(hunks: Sequence[PatchHunk]) -> bool:
    return any(
        line.kind in {PatchHunkLineKind.DELETE, PatchHunkLineKind.INSERT} for hunk in hunks for line in hunk.lines
    )


def _change_summary(action: PatchAction) -> PatchChangeSummary:
    return PatchChangeSummary(
        index=action.index,
        operation=action.kind,
        path=action.path,
        destination_path=action.destination_path,
        hunks=len(action.hunks),
    )


def _digest(value: str) -> str:
    return PLAN_DIGEST_PREFIX + sha256(value.encode("utf-8")).hexdigest()
