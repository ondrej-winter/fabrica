"""Fail-closed POSIX workspace search-scope resolution primitives."""

from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.path_resolution import (
    SearchScope,
    SearchScopeKind,
    SearchScopeResolutionError,
    resolve_search_scope,
)

__all__ = [
    "SearchScope",
    "SearchScopeKind",
    "SearchScopeResolutionError",
    "resolve_search_scope",
]
