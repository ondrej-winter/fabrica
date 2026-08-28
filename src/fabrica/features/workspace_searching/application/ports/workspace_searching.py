"""Application-owned ports for bounded workspace source discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from fabrica.features.workspace_searching.application.dtos import (
        SearchCodebaseCommand,
        SearchCodebaseResult,
        SearchLimits,
        SearchQuery,
        SearchQueryResult,
    )


class WorkspaceSearchCancellationSignal(Protocol):
    """Cancellation boundary that search execution must observe."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether the host has requested cancellation."""
        ...


@dataclass(frozen=True, slots=True)
class WorkspaceSearchContext:
    """Host-supplied execution bounds for one workspace-searching batch."""

    cancellation: WorkspaceSearchCancellationSignal
    deadline_at: datetime | None
    limits: SearchLimits

    def __post_init__(self) -> None:
        if self.deadline_at is not None and self.deadline_at.tzinfo is None:
            msg = "deadline_at must be timezone-aware"
            raise ValueError(msg)


class SearchCodebasePort(Protocol):
    """Inbound port for one normalized batch of workspace source searches."""

    async def search(self, command: SearchCodebaseCommand, context: WorkspaceSearchContext) -> SearchCodebaseResult:
        """Search workspace source under host-supplied bounds."""
        ...


class WorkspaceSearchBackend(Protocol):
    """Outbound port for one canonical query against a safely contained workspace."""

    async def search_query(self, query: SearchQuery, context: WorkspaceSearchContext) -> SearchQueryResult:
        """Execute one query and return either matches or a structured failure."""
        ...


__all__ = [
    "SearchCodebasePort",
    "WorkspaceSearchBackend",
    "WorkspaceSearchCancellationSignal",
    "WorkspaceSearchContext",
]
