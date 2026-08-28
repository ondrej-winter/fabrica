"""Pure bounded rendering for numbered workspace text output."""

from collections.abc import Iterable
from dataclasses import dataclass

from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits
from fabrica.features.workspace_reading.application.output_limiting import (
    fits_output_limit,
    truncate_line_content,
)
from fabrica.features.workspace_reading.application.validation import TextLineRange


@dataclass(frozen=True, slots=True)
class FormattedTextRead:
    """Rendered text and explicit pagination state for one normalized range."""

    content: str
    start_line: int | None
    end_line: int | None
    complete: bool
    next_start_line: int | None
    truncated_lines: tuple[int, ...]

    def __post_init__(self) -> None:
        truncated_lines = tuple(self.truncated_lines)
        _validate_result_pagination(self)
        _validate_result_lines(self)
        _validate_truncated_lines(self, truncated_lines)
        object.__setattr__(self, "truncated_lines", truncated_lines)


def format_text_lines(lines: Iterable[str], *, line_range: TextLineRange, limits: ReadFilesLimits) -> FormattedTextRead:
    """Render a bounded inclusive range of source lines with explicit continuation metadata."""
    iterator = enumerate(lines, start=1)
    current = _first_requested_line(iterator, start_line=line_range.start_line)
    if current is None:
        return _empty_complete_result()

    accumulator = _TextReadAccumulator(limits=limits)
    while current is not None:
        line_number, line = current
        if line_range.end_line is not None and line_number > line_range.end_line:
            return accumulator.result(complete=True)
        if not accumulator.append(line_number, line):
            return accumulator.result(complete=False, next_start_line=line_number)
        if line_range.end_line == line_number:
            return accumulator.result(complete=True)
        current = _next_line(iterator)
        if accumulator.line_count == limits.max_read_lines:
            return accumulator.result_after_line_limit(current)
    return accumulator.result(complete=True)


@dataclass(slots=True)
class _TextReadAccumulator:
    """Mutable local state for constructing one bounded formatted text result."""

    limits: ReadFilesLimits
    rendered_lines: list[str]
    truncated_lines: list[int]

    def __init__(self, *, limits: ReadFilesLimits) -> None:
        self.limits = limits
        self.rendered_lines = []
        self.truncated_lines = []

    @property
    def line_count(self) -> int:
        """Return the count of completely rendered source lines."""
        return len(self.rendered_lines)

    def append(self, line_number: int, line: str) -> bool:
        """Append one source line when it fits the output budget."""
        rendered_content, was_truncated = truncate_line_content(line, limits=self.limits)
        candidate = f"{line_number} | {rendered_content}"
        if not fits_output_limit(
            "\n".join(self.rendered_lines), candidate, max_output_chars=self.limits.max_output_chars_per_file
        ):
            return False
        self.rendered_lines.append(candidate)
        if was_truncated:
            self.truncated_lines.append(line_number)
        return True

    def result_after_line_limit(self, next_line: tuple[int, str] | None) -> FormattedTextRead:
        """Build completion metadata after reaching the configured line cap."""
        if next_line is None:
            return self.result(complete=True)
        return self.result(complete=False, next_start_line=next_line[0])

    def result(self, *, complete: bool, next_start_line: int | None = None) -> FormattedTextRead:
        """Build an immutable result from accumulated rendered lines."""
        if not self.rendered_lines and not complete:
            return FormattedTextRead(
                content="",
                start_line=None,
                end_line=None,
                complete=False,
                next_start_line=next_start_line,
                truncated_lines=(),
            )
        return _formatted_result(
            self.rendered_lines,
            self.truncated_lines,
            complete=complete,
            next_start_line=next_start_line,
        )


def _first_requested_line(iterator: Iterable[tuple[int, str]], *, start_line: int) -> tuple[int, str] | None:
    return next((line for line in iterator if line[0] >= start_line), None)


def _next_line(iterator: Iterable[tuple[int, str]]) -> tuple[int, str] | None:
    return next(iter(iterator), None)


def _empty_complete_result() -> FormattedTextRead:
    return FormattedTextRead(
        content="",
        start_line=None,
        end_line=None,
        complete=True,
        next_start_line=None,
        truncated_lines=(),
    )


def _validate_result_pagination(result: FormattedTextRead) -> None:
    if result.complete != (result.next_start_line is None):
        msg = "pagination metadata must match complete"
        raise ValueError(msg)
    if result.next_start_line is None:
        return
    expected_next = result.next_start_line
    if result.start_line is not None and result.end_line is not None:
        expected_next = result.end_line + 1
    if result.next_start_line < 1 or result.next_start_line != expected_next:
        msg = "next_start_line must point to the next unread line"
        raise ValueError(msg)


def _validate_result_lines(result: FormattedTextRead) -> None:
    if result.start_line is None and result.end_line is not None:
        msg = "empty output must not have an end line"
        raise ValueError(msg)
    if result.start_line is not None and result.end_line is None:
        msg = "non-empty output must have an end line"
        raise ValueError(msg)
    if result.start_line is not None and result.end_line is not None and result.end_line < result.start_line:
        msg = "end_line must not precede start_line"
        raise ValueError(msg)


def _validate_truncated_lines(result: FormattedTextRead, truncated_lines: tuple[int, ...]) -> None:
    if result.start_line is None and truncated_lines:
        msg = "empty output must not have truncated lines"
        raise ValueError(msg)
    if (
        result.start_line is not None
        and result.end_line is not None
        and any(line < result.start_line or line > result.end_line for line in truncated_lines)
    ):
        msg = "truncated lines must be returned lines"
        raise ValueError(msg)
    if tuple(sorted(set(truncated_lines))) != truncated_lines:
        msg = "truncated lines must be ordered and unique"
        raise ValueError(msg)


def _formatted_result(
    rendered_lines: list[str],
    truncated_lines: list[int],
    *,
    complete: bool,
    next_start_line: int | None = None,
) -> FormattedTextRead:
    start_line = _line_number(rendered_lines[0]) if rendered_lines else None
    end_line = _line_number(rendered_lines[-1]) if rendered_lines else None
    return FormattedTextRead(
        content="\n".join(rendered_lines),
        start_line=start_line,
        end_line=end_line,
        complete=complete,
        next_start_line=next_start_line,
        truncated_lines=tuple(truncated_lines),
    )


def _line_number(rendered_line: str) -> int:
    return int(rendered_line.partition(" | ")[0])


__all__ = ["FormattedTextRead", "format_text_lines"]
