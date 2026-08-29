"""Convert backend-neutral match locations into bounded source context."""

from collections.abc import Mapping

from fabrica.features.workspace_searching.application.dtos import (
    SearchContextLine,
    SearchLimits,
    SearchLocation,
    SearchMatch,
)
from fabrica.features.workspace_searching.application.output_limiting import truncate_line_content


def hydrate_search_locations(
    locations: tuple[SearchLocation, ...],
    source_text_by_path: Mapping[str, str],
    *,
    limits: SearchLimits,
) -> tuple[SearchMatch, ...]:
    """Return stable, bounded matches from backend locations and loaded source text.

    The backend's byte offset is converted against the original UTF-8 source
    line, before long-line truncation. Repeated backend locations on one source
    line intentionally collapse to the earliest column because Version 1 returns
    one match object per matching line.
    """
    matches: list[SearchMatch] = []
    emitted_lines: set[tuple[str, int]] = set()
    for location in sorted(locations, key=lambda item: (item.path, item.line, item.column_byte_offset)):
        line_key = (location.path, location.line)
        if line_key in emitted_lines:
            continue
        source_text = _source_text_for(location.path, source_text_by_path)
        lines = source_text.splitlines()
        if location.line > len(lines):
            msg = f"backend location line is outside source text: {location.path}:{location.line}"
            raise ValueError(msg)
        source_line = lines[location.line - 1]
        matches.append(
            SearchMatch(
                path=location.path,
                line=location.line,
                column=_unicode_column(source_line, location.column_byte_offset),
                text=_bounded_context_text(source_line, limits),
                text_truncated=len(source_line) > limits.max_line_chars,
                before=_context_before(lines, location.line, limits),
                after=_context_after(lines, location.line, limits),
            )
        )
        emitted_lines.add(line_key)
    return tuple(matches)


def _source_text_for(path: str, source_text_by_path: Mapping[str, str]) -> str:
    try:
        source_text = source_text_by_path[path]
    except KeyError as err:
        msg = f"source text is unavailable for backend location: {path}"
        raise ValueError(msg) from err
    if not isinstance(source_text, str):
        msg = f"source text must be a string: {path}"
        raise TypeError(msg)
    return source_text


def _unicode_column(source_line: str, byte_offset: int) -> int:
    source_bytes = source_line.encode("utf-8")
    if byte_offset > len(source_bytes):
        msg = "backend byte offset is outside the source line"
        raise ValueError(msg)
    try:
        prefix = source_bytes[:byte_offset].decode("utf-8")
    except UnicodeDecodeError as err:
        msg = "backend byte offset does not identify a Unicode character boundary"
        raise ValueError(msg) from err
    return len(prefix) + 1


def _context_before(lines: list[str], match_line: int, limits: SearchLimits) -> tuple[SearchContextLine, ...]:
    start = max(1, match_line - limits.context_lines)
    return tuple(_context_line(line_number, lines[line_number - 1], limits) for line_number in range(start, match_line))


def _context_after(lines: list[str], match_line: int, limits: SearchLimits) -> tuple[SearchContextLine, ...]:
    end = min(len(lines), match_line + limits.context_lines)
    return tuple(
        _context_line(line_number, lines[line_number - 1], limits) for line_number in range(match_line + 1, end + 1)
    )


def _context_line(line_number: int, source_line: str, limits: SearchLimits) -> SearchContextLine:
    text, text_truncated = truncate_line_content(source_line, limits=limits)
    return SearchContextLine(line=line_number, text=text, text_truncated=text_truncated)


def _bounded_context_text(source_line: str, limits: SearchLimits) -> str:
    text, _ = truncate_line_content(source_line, limits=limits)
    return text


__all__ = ["hydrate_search_locations"]
