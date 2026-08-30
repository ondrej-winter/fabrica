"""Canonical, fail-closed literal workspace search-scope resolution."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from fabrica.features.workspace_searching.application.dtos import SearchErrorCode


class SearchScopeKind(StrEnum):
    """The filesystem object that bounds one literal search query."""

    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True, slots=True)
class SearchScope:
    """A canonical existing scope known to remain below the workspace root."""

    canonical_path: Path
    workspace_relative_path: str
    kind: SearchScopeKind


@dataclass(frozen=True, slots=True)
class SearchScopeResolutionError(Exception):
    """Stable application error category for a rejected search scope."""

    code: SearchErrorCode
    message: str

    def __str__(self) -> str:
        return self.message


def resolve_search_scope(workspace_root: Path, requested_path: str) -> SearchScope:
    """Resolve one existing literal file or directory without permitting workspace escape.

    This resolution provides best-effort pre-launch containment. A malicious local
    process can still replace paths after validation and during recursive search.
    """
    _validate_requested_path(requested_path)
    root = _resolve_workspace_root(workspace_root)
    candidate = root if requested_path == "." else root / requested_path
    try:
        canonical_path = candidate.resolve(strict=True)
    except FileNotFoundError as err:
        raise SearchScopeResolutionError(SearchErrorCode.NOT_FOUND, "workspace path does not exist") from err
    except OSError as err:
        raise SearchScopeResolutionError(SearchErrorCode.IO_ERROR, "workspace path could not be resolved") from err
    if not canonical_path.is_relative_to(root):
        raise SearchScopeResolutionError(SearchErrorCode.PATH_OUTSIDE_WORKSPACE, "path escapes the workspace")
    try:
        if canonical_path.is_file():
            kind = SearchScopeKind.FILE
        elif canonical_path.is_dir():
            if requested_path != "." and candidate.is_symlink():
                msg = "symlinked directories are not valid recursive search scopes"
                raise SearchScopeResolutionError(SearchErrorCode.INVALID_PATH, msg)
            kind = SearchScopeKind.DIRECTORY
        else:
            raise SearchScopeResolutionError(SearchErrorCode.INVALID_PATH, "path is not a regular file or directory")
    except OSError as err:
        raise SearchScopeResolutionError(SearchErrorCode.IO_ERROR, "workspace path could not be inspected") from err
    return SearchScope(canonical_path, str(canonical_path.relative_to(root)) or ".", kind)


def _validate_requested_path(requested_path: str) -> None:
    if not isinstance(requested_path, str) or not requested_path or requested_path.startswith(("/", "\\")):
        msg = "path must be a non-empty workspace-relative path"
        raise SearchScopeResolutionError(SearchErrorCode.INVALID_PATH, msg)
    if "\\" in requested_path:
        msg = "path must use POSIX workspace-relative separators"
        raise SearchScopeResolutionError(SearchErrorCode.INVALID_PATH, msg)
    if ".." in requested_path.split("/"):
        raise SearchScopeResolutionError(SearchErrorCode.PATH_OUTSIDE_WORKSPACE, "path escapes the workspace")


def _resolve_workspace_root(workspace_root: Path) -> Path:
    try:
        root = workspace_root.resolve(strict=True)
    except FileNotFoundError as err:
        raise SearchScopeResolutionError(SearchErrorCode.NOT_FOUND, "workspace root does not exist") from err
    except OSError as err:
        raise SearchScopeResolutionError(SearchErrorCode.IO_ERROR, "workspace root could not be resolved") from err
    if not root.is_dir():
        raise SearchScopeResolutionError(SearchErrorCode.INVALID_PATH, "workspace root must be a directory")
    return root


__all__ = ["SearchScope", "SearchScopeKind", "SearchScopeResolutionError", "resolve_search_scope"]
