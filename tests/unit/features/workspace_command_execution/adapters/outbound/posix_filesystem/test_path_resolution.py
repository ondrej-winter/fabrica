"""Tests for workspace-contained command current-directory resolution."""

from pathlib import Path

import pytest

from fabrica.features.workspace_command_execution.adapters.outbound.posix_filesystem import (
    PosixWorkspaceCommandResolver,
)
from fabrica.features.workspace_command_execution.application.dtos import CommandErrorCode
from fabrica.features.workspace_command_execution.application.errors import CommandPlanningError

SYNTHETIC_RESOLUTION_FAILURE = "synthetic resolution failure"
SYNTHETIC_INSPECTION_FAILURE = "synthetic inspection failure"
SYNTHETIC_ROOT_FAILURE = "synthetic root failure"


def test_resolves_root_and_nested_directories_to_canonical_workspace_relative_paths(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "child"
    nested.mkdir(parents=True)
    resolver = PosixWorkspaceCommandResolver(tmp_path)

    assert resolver.resolve_cwd(".") == "."
    assert resolver.resolve_cwd("nested/child") == "nested/child"


@pytest.mark.parametrize(
    "requested_cwd",
    [None, "", "../outside", "/outside", "\\outside", "C:\\outside", "nested\\child"],
)
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


@pytest.mark.parametrize("root_kind", ["missing", "file"])
def test_rejects_missing_or_non_directory_workspace_roots(tmp_path: Path, root_kind: str) -> None:
    root = tmp_path / "missing" if root_kind == "missing" else tmp_path / "root.txt"
    if root_kind == "file":
        root.write_text("not a directory")

    with pytest.raises(CommandPlanningError) as raised:
        PosixWorkspaceCommandResolver(root).resolve_cwd(".")

    assert raised.value.code is CommandErrorCode.INVALID_CWD


def test_maps_os_errors_while_resolving_or_inspecting_a_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    candidate = tmp_path / "nested"
    candidate.mkdir()
    resolver = PosixWorkspaceCommandResolver(tmp_path)
    original_resolve = Path.resolve
    original_is_dir = Path.is_dir

    def fail_candidate_resolution(path: Path, *, strict: bool = False) -> Path:
        if path == candidate:
            raise OSError(SYNTHETIC_RESOLUTION_FAILURE)
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", fail_candidate_resolution)
    with pytest.raises(CommandPlanningError, match="could not be resolved"):
        resolver.resolve_cwd("nested")

    monkeypatch.setattr(Path, "resolve", original_resolve)

    def fail_candidate_inspection(path: Path) -> bool:
        if path == candidate:
            raise OSError(SYNTHETIC_INSPECTION_FAILURE)
        return original_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", fail_candidate_inspection)
    with pytest.raises(CommandPlanningError, match="could not be inspected"):
        resolver.resolve_cwd("nested")


def test_maps_workspace_root_resolution_os_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    original_resolve = Path.resolve

    def fail_root_resolution(path: Path, *, strict: bool = False) -> Path:
        if path == tmp_path:
            raise OSError(SYNTHETIC_ROOT_FAILURE)
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", fail_root_resolution)

    with pytest.raises(CommandPlanningError, match="workspace root could not be resolved"):
        PosixWorkspaceCommandResolver(tmp_path).resolve_cwd(".")
