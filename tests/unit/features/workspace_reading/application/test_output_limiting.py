"""Tests for pure workspace-reading output limits."""

from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits
from fabrica.features.workspace_reading.application.output_limiting import fits_output_limit, truncate_line_content


def test_truncate_line_content_keeps_limit_prefix_and_visible_marker() -> None:
    content, truncated = truncate_line_content("abcdef", limits=ReadFilesLimits(max_line_chars=3))

    assert content == "abc … [line truncated]"
    assert truncated is True


def test_fits_output_limit_accounts_for_newline_between_rendered_lines() -> None:
    assert fits_output_limit("1 | first", "2 | second", max_output_chars=20) is True
    assert fits_output_limit("1 | first", "2 | second", max_output_chars=19) is False
