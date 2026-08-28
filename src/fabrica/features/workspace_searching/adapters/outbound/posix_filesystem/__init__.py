"""Fail-closed POSIX scope and subprocess-containment primitives."""

from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.path_resolution import (
    SearchScope,
    SearchScopeKind,
    SearchScopeResolutionError,
    resolve_search_scope,
)
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.search_sandbox import (
    SearchSandbox,
    SearchSandboxUnavailableError,
)

__all__ = [
    "SearchSandbox",
    "SearchSandboxUnavailableError",
    "SearchScope",
    "SearchScopeKind",
    "SearchScopeResolutionError",
    "resolve_search_scope",
]
