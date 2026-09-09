"""Tests for workspace search-scope value types."""

from pathlib import Path

from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.scope import SearchScope, SearchScopeKind


def test_search_scope_kind_uses_stable_serialized_values() -> None:
    assert SearchScopeKind.FILE.value == "file"
    assert SearchScopeKind.DIRECTORY.value == "directory"


def test_search_scope_retains_its_canonical_scope_data() -> None:
    canonical_path = Path("/workspace/src/app.py")

    scope = SearchScope(canonical_path, "src/app.py", SearchScopeKind.FILE)

    assert scope.canonical_path == canonical_path
    assert scope.workspace_relative_path == "src/app.py"
    assert scope.kind is SearchScopeKind.FILE
