"""Fail-closed POSIX workspace search-scope resolution primitives."""

from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.errors import SearchScopeResolutionError
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.resolver import resolve_search_scope
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.scope import SearchScope, SearchScopeKind

__all__ = [
    "SearchScope",
    "SearchScopeKind",
    "SearchScopeResolutionError",
    "resolve_search_scope",
]
