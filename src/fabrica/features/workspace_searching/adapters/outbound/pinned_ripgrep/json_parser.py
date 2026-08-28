"""Translate ripgrep's JSON-lines match events into neutral search locations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fabrica.features.workspace_searching.application.dtos import SearchLocation

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


@dataclass(frozen=True, slots=True)
class RipgrepJsonEventError(Exception):
    """Raised when a purported ripgrep JSON event cannot be safely interpreted."""

    message: str

    def __str__(self) -> str:
        return self.message


def parse_ripgrep_json_events(events: Iterable[str]) -> Iterator[SearchLocation]:
    """Yield one location per ripgrep matching-line event without buffering output."""
    for event in events:
        location = parse_ripgrep_json_event(event)
        if location is not None:
            yield location


def parse_ripgrep_json_event(event: str) -> SearchLocation | None:
    """Parse one JSON-lines event, ignoring non-match events from ripgrep."""
    try:
        payload = json.loads(event)
    except json.JSONDecodeError as err:
        msg = "ripgrep emitted malformed JSON"
        raise RipgrepJsonEventError(msg) from err
    if not isinstance(payload, dict):
        msg = "ripgrep emitted a non-object JSON event"
        raise RipgrepJsonEventError(msg)
    if payload.get("type") != "match":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        msg = "ripgrep match event is malformed"
        raise RipgrepJsonEventError(msg)
    path = _text_field(data.get("path"), field_name="path")
    line = data.get("line_number")
    submatches = data.get("submatches")
    if not isinstance(line, int) or line < 1 or not isinstance(submatches, list) or not submatches:
        msg = "ripgrep match event is malformed"
        raise RipgrepJsonEventError(msg)
    first_submatch = submatches[0]
    if not isinstance(first_submatch, dict):
        msg = "ripgrep match event is malformed"
        raise RipgrepJsonEventError(msg)
    start = first_submatch.get("start")
    if not isinstance(start, int) or start < 0:
        msg = "ripgrep match event is malformed"
        raise RipgrepJsonEventError(msg)
    matched_text = _text_field(first_submatch.get("match"), field_name="match")
    return SearchLocation(path=path, line=line, column_byte_offset=start, matched_text=matched_text)


def _text_field(value: object, *, field_name: str) -> str:
    if not isinstance(value, dict):
        msg = "ripgrep match event is malformed"
        raise RipgrepJsonEventError(msg)
    text = value.get("text")
    if not isinstance(text, str) or not text:
        msg = f"ripgrep {field_name} must be UTF-8 text"
        raise RipgrepJsonEventError(msg)
    return text


__all__ = ["RipgrepJsonEventError", "parse_ripgrep_json_event", "parse_ripgrep_json_events"]
