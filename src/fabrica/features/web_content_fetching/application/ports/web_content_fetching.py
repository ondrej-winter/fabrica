"""Application-owned ports for bounded public web-content retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from fabrica.features.web_content_fetching.application.dtos import (
        FetchAttemptOutcome,
        FetchWebContentCommand,
        FetchWebContentLimits,
        FetchWebContentRequest,
        FetchWebContentResult,
    )


class FetchCancellationSignal(Protocol):
    """Cancellation boundary that public-web retrieval must observe."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether the host has requested cancellation."""
        ...


@dataclass(frozen=True, slots=True)
class FetchWebContentContext:
    """Host-supplied access policy and execution bounds for one fetch batch."""

    public_web_enabled: bool
    cancellation: FetchCancellationSignal
    deadline_at: datetime | None
    limits: FetchWebContentLimits

    def __post_init__(self) -> None:
        if not isinstance(self.public_web_enabled, bool):
            msg = "public_web_enabled must be a boolean"
            raise TypeError(msg)
        if self.deadline_at is not None and self.deadline_at.tzinfo is None:
            msg = "deadline_at must be timezone-aware"
            raise ValueError(msg)


class FetchWebContentPort(Protocol):
    """Inbound port for one normalized public-web fetch batch."""

    async def fetch(self, command: FetchWebContentCommand, context: FetchWebContentContext) -> FetchWebContentResult:
        """Fetch ordered requests under host-supplied access policy and limits."""
        ...


class PublicDnsResolver(Protocol):
    """Outbound port for resolving one hostname before destination validation."""

    async def resolve(self, hostname: str, context: FetchWebContentContext) -> tuple[str, ...]:
        """Resolve hostname addresses without exposing resolver implementation types."""
        ...


class WebContentAttemptFetcher(Protocol):
    """Outbound port for one already-validated, GET-only fetch attempt."""

    async def fetch_attempt(
        self, request: FetchWebContentRequest, context: FetchWebContentContext
    ) -> FetchAttemptOutcome:
        """Return a typed streamed-attempt outcome without retry orchestration."""
        ...


__all__ = [
    "FetchCancellationSignal",
    "FetchWebContentContext",
    "FetchWebContentPort",
    "PublicDnsResolver",
    "WebContentAttemptFetcher",
]
