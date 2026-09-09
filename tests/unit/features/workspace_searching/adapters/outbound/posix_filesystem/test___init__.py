"""Tests for the workspace-searching POSIX filesystem package API."""

from fabrica.features.workspace_searching.adapters.outbound import posix_filesystem
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import errors, resolver, scope


def test_exports_the_supported_workspace_search_scope_api() -> None:
    assert posix_filesystem.__all__ == [
        "SearchScope",
        "SearchScopeKind",
        "SearchScopeResolutionError",
        "resolve_search_scope",
    ]
    assert posix_filesystem.SearchScope is scope.SearchScope
    assert posix_filesystem.SearchScopeKind is scope.SearchScopeKind
    assert posix_filesystem.SearchScopeResolutionError is errors.SearchScopeResolutionError
    assert posix_filesystem.resolve_search_scope is resolver.resolve_search_scope
