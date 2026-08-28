"""Tests for pure workspace-searching output limits."""

from fabrica.features.workspace_searching.application.dtos import SearchLimits
from fabrica.features.workspace_searching.application.output_limiting import (
    fits_serialized_output_limit,
    truncate_line_content,
)


def test_truncate_line_content_keeps_limit_prefix_and_visible_marker() -> None:
    content, truncated = truncate_line_content("abcdef", limits=SearchLimits(max_line_chars=3))

    assert content == "abc … [line truncated]"
    assert truncated is True


def test_truncate_line_content_preserves_short_lines() -> None:
    content, truncated = truncate_line_content("abc", limits=SearchLimits(max_line_chars=3))

    assert content == "abc"
    assert truncated is False


def test_fits_serialized_output_limit_accounts_for_complete_object_and_separator() -> None:
    assert fits_serialized_output_limit('{"path":"a"}', {"path": "b"}, max_output_chars=25) is True
    assert fits_serialized_output_limit('{"path":"a"}', {"path": "b"}, max_output_chars=24) is False
