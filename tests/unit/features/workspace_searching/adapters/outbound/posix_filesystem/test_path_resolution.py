"""Tests for literal workspace search-scope resolution."""

import os
from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import (
    SearchScopeKind,
    SearchScopeResolutionError,
    resolve_search_scope,
)
from fabrica.features.workspace_searching.application.dtos import SearchErrorCode


def test_resolve_search_scope_returns_canonical_file_and_directory_scopes(tmp_path: Path) -> None:
    source_file = tmp_path / "src" / "app.py"
    source_file.parent.mkdir()
    source_file.write_text("value = 1\n", encoding="utf-8")

    file_scope = resolve_search_scope(tmp_path, "src/app.py")
    directory_scope = resolve_search_scope(tmp_path, "src")
    root_scope = resolve_search_scope(tmp_path, ".")

    assert (file_scope.workspace_relative_path, file_scope.kind) == ("src/app.py", SearchScopeKind.FILE)
    assert (directory_scope.workspace_relative_path, directory_scope.kind) == ("src", SearchScopeKind.DIRECTORY)
    assert (root_scope.workspace_relative_path, root_scope.kind) == (".", SearchScopeKind.DIRECTORY)


@pytest.mark.parametrize(
    ("requested_path", "expected_code"),
    [
        ("/etc/passwd", SearchErrorCode.INVALID_PATH),
        ("../outside", SearchErrorCode.PATH_OUTSIDE_WORKSPACE),
        ("C:\\outside", SearchErrorCode.INVALID_PATH),
        ("missing.py", SearchErrorCode.NOT_FOUND),
    ],
)
def test_resolve_search_scope_rejects_invalid_or_missing_paths(
    tmp_path: Path, requested_path: str, expected_code: SearchErrorCode
) -> None:
    with pytest.raises(SearchScopeResolutionError) as exc_info:
        resolve_search_scope(tmp_path, requested_path)

    assert exc_info.value.code is expected_code


def test_resolve_search_scope_rejects_symlink_escape_special_files_and_directory_symlinks(tmp_path: Path) -> None:
    outside = tmp_path.parent / "search-outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (tmp_path / "escape.txt").symlink_to(outside)
    (tmp_path / "internal").mkdir()
    (tmp_path / "directory-link").symlink_to("internal", target_is_directory=True)
    os.mkfifo(tmp_path / "named-pipe")

    for requested_path, expected_code in (
        ("escape.txt", SearchErrorCode.PATH_OUTSIDE_WORKSPACE),
        ("directory-link", SearchErrorCode.INVALID_PATH),
        ("named-pipe", SearchErrorCode.INVALID_PATH),
    ):
        with pytest.raises(SearchScopeResolutionError) as exc_info:
            resolve_search_scope(tmp_path, requested_path)
        assert exc_info.value.code is expected_code


def test_resolve_search_scope_allows_an_explicit_internal_symlinked_file(tmp_path: Path) -> None:
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "app-link.py").symlink_to("src/app.py")

    scope = resolve_search_scope(tmp_path, "app-link.py")

    assert scope.workspace_relative_path == "src/app.py"
    assert scope.kind is SearchScopeKind.FILE
