"""Tests for workspace-contained command current-directory resolution."""

from pathlib import Path

import pytest

from fabrica.features.workspace_command_execution.adapters.outbound.posix_filesystem import (
    PosixWorkspaceCommandResolver,
)
from fabrica.features.workspace_command_execution.application.dtos import CommandErrorCode
from fabrica.features.workspace_command_execution.application.errors import CommandPlanningError


def test_resolves_root_and_nested_directories_to_canonical_workspace_relative_paths(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "child"
    nested.mkdir(parents=True)
    resolver = PosixWorkspaceCommandResolver(tmp_path)

    assert resolver.resolve_cwd(".") == "."
    assert resolver.resolve_cwd("nested/child") == "nested/child"


@pytest.mark.parametrize("requested_cwd", ["../outside", "/outside", "C:\\outside", "nested\\child"])
def test_rejects_traversal_and_platform_absolute_or_backslash_paths(tmp_path: Path, requested_cwd: str) -> None:
    resolver = PosixWorkspaceCommandResolver(tmp_path)

    with pytest.raises(CommandPlanningError) as raised:
        resolver.resolve_cwd(requested_cwd)

    assert raised.value.code in {CommandErrorCode.INVALID_CWD, CommandErrorCode.CWD_OUTSIDE_WORKSPACE}


def test_rejects_missing_non_directory_and_symlink_escape_paths(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    file_path = tmp_path / "file.txt"
    file_path.write_text("content")
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    resolver = PosixWorkspaceCommandResolver(tmp_path)

    for requested_cwd, code in (
        ("missing", CommandErrorCode.INVALID_CWD),
        ("file.txt", CommandErrorCode.INVALID_CWD),
        ("escape", CommandErrorCode.CWD_OUTSIDE_WORKSPACE),
    ):
        with pytest.raises(CommandPlanningError) as raised:
            resolver.resolve_cwd(requested_cwd)
        assert raised.value.code is code
