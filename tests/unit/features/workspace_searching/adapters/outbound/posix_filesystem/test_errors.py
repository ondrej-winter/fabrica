"""Tests for workspace search-scope resolution errors."""

from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.errors import SearchScopeResolutionError
from fabrica.features.workspace_searching.application.dtos import SearchErrorCode


def test_search_scope_resolution_error_exposes_its_stable_category_and_message() -> None:
    error = SearchScopeResolutionError(SearchErrorCode.INVALID_PATH, "path must be workspace-relative")

    assert error.code is SearchErrorCode.INVALID_PATH
    assert error.message == "path must be workspace-relative"
    assert str(error) == "path must be workspace-relative"
