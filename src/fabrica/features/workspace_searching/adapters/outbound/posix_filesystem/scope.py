"""Value types describing canonical workspace search scopes."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


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


__all__ = ["SearchScope", "SearchScopeKind"]
