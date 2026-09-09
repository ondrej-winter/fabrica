"""Stable errors for POSIX workspace search-scope resolution."""

from dataclasses import dataclass

from fabrica.features.workspace_searching.application.dtos import SearchErrorCode


@dataclass(frozen=True, slots=True)
class SearchScopeResolutionError(Exception):
    """Stable application error category for a rejected search scope."""

    code: SearchErrorCode
    message: str

    def __str__(self) -> str:
        return self.message


__all__ = ["SearchScopeResolutionError"]
