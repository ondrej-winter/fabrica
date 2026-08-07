"""Tests for read-only git context parsing helpers."""

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.context_parsing import (
    parse_ahead_behind_counts,
    parse_commit_details,
    parse_commit_log,
    parse_context_name_status_line,
    parse_merge_base,
    parse_status_summary,
)
from fabrica.features.developer_workflow.application.dtos import GitContextChangedFileStatus

EXPECTED_MULTIPLE_COUNT = 2


def test_context_name_status_parser_maps_regular_renamed_and_copied_records() -> None:
    modified = parse_context_name_status_line("M\tsrc/file.py")
    renamed = parse_context_name_status_line("R100\told.py\tnew.py")
    copied = parse_context_name_status_line("C075\tsrc/base.py\tsrc/copy.py")

    assert (modified.status, modified.path, modified.old_path) == (
        GitContextChangedFileStatus.MODIFIED,
        "src/file.py",
        None,
    )
    assert (renamed.status, renamed.path, renamed.old_path) == (
        GitContextChangedFileStatus.RENAMED,
        "new.py",
        "old.py",
    )
    assert (copied.status, copied.path, copied.old_path) == (
        GitContextChangedFileStatus.COPIED,
        "src/copy.py",
        "src/base.py",
    )


@pytest.mark.parametrize("line", ["", "X\tfile.py", "M", "M\tone.py\ttwo.py", "R100\told.py"])
def test_context_name_status_parser_rejects_unsupported_records(line: str) -> None:
    with pytest.raises(ValueError, match=r"git context|supported|record|paths"):
        parse_context_name_status_line(line)


def test_status_summary_parser_maps_branch_counts_and_bounded_untracked_paths() -> None:
    summary = parse_status_summary(
        "## feature/read-only...origin/feature/read-only [ahead 1]\n"
        "M  staged.py\n"
        " M unstaged.py\n"
        "MM both.py\n"
        "?? notes.txt\n"
        "?? scratch.md\n",
        head_short_hash="abc1234",
        max_untracked_paths=1,
    )

    assert summary.branch == "feature/read-only"
    assert summary.upstream == "origin/feature/read-only"
    assert summary.head_short_hash == "abc1234"
    assert summary.is_detached is False
    assert summary.staged_count == EXPECTED_MULTIPLE_COUNT
    assert summary.unstaged_count == EXPECTED_MULTIPLE_COUNT
    assert summary.untracked_count == EXPECTED_MULTIPLE_COUNT
    assert summary.untracked_paths == ("notes.txt",)


def test_status_summary_parser_handles_detached_head() -> None:
    summary = parse_status_summary("## HEAD (no branch)\n M file.py\n", head_short_hash="abc1234")

    assert summary.branch is None
    assert summary.is_detached is True
    assert summary.unstaged_count == 1


def test_commit_log_parser_maps_records_and_ref_decorations() -> None:
    log = parse_commit_log(
        "abcdef123456\x1fabcdef1\x1fAdd parser\x1f2026-08-07T18:00:00+00:00\x1fHEAD -> main, tag: v1\x1e"
        "123456abcdef\x1f123456a\x1fInitial\x1f2026-08-06T18:00:00+00:00\x1f\x1e"
    )

    assert [(commit.short_hash, commit.subject, commit.refs) for commit in log.commits] == [
        ("abcdef1", "Add parser", ("HEAD -> main", "tag: v1")),
        ("123456a", "Initial", ()),
    ]


def test_commit_details_parser_maps_metadata_and_body() -> None:
    details = parse_commit_details(
        "abcdef123456\x1fabcdef1\x1fparent1 parent2\x1fAda <ada@example.com>\x1f"
        "2026-08-07T18:00:00+00:00\x1f2026-08-07T18:01:00+00:00\x1f"
        "Add parser\x1fHEAD -> main\x1fBody line 1\nBody line 2"
    )

    assert details.commit_hash == "abcdef123456"
    assert details.parents == ("parent1", "parent2")
    assert details.refs == ("HEAD -> main",)
    assert details.body == "Body line 1\nBody line 2"


def test_ahead_behind_and_merge_base_parsers_map_fixed_outputs() -> None:
    ahead_behind = parse_ahead_behind_counts("2\t1\n", current_branch="feature", base_ref="origin/main")
    merge_base = parse_merge_base("abcdef1234567890\n")

    assert ahead_behind.current_branch == "feature"
    assert ahead_behind.base_ref == "origin/main"
    assert ahead_behind.ahead_count == 1
    assert ahead_behind.behind_count == EXPECTED_MULTIPLE_COUNT
    assert merge_base.commit_hash == "abcdef1234567890"
    assert merge_base.short_hash == "abcdef1"


@pytest.mark.parametrize("output", ["", "one-field", "a\x1ftoo-few"])
def test_commit_parsers_reject_malformed_output(output: str) -> None:
    with pytest.raises(ValueError, match=r"record|output"):
        parse_commit_log(output)
    with pytest.raises(ValueError, match="output"):
        parse_commit_details(output)
