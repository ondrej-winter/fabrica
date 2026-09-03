"""Application-owned completion persistence and presentation ports."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos.completion import CompletionCommitResult, CompletionRecord


class CompletionGuard(Protocol):
    """Host-owned policy that may block a proposed terminal completion."""

    async def evaluate(self, record: CompletionRecord) -> str | None:
        """Return a safe block reason, or ``None`` when completion may proceed."""
        ...


class CompletionStore(Protocol):
    """Atomically persists terminal records with their run-state transition."""

    async def commit_completion(self, run_id: str, record: CompletionRecord) -> CompletionCommitResult:
        """Persist ``record`` and compare-and-set its run from running to completed."""
        ...

    async def list_unpresented(self) -> tuple[CompletionRecord, ...]:
        """List durable committed records without a presentation acknowledgement."""
        ...

    async def acknowledge_presented(self, run_id: str) -> bool:
        """Durably acknowledge one presented completion record exactly once."""
        ...


class CompletionPresenter(Protocol):
    """Host-facing port that renders an already committed completion summary."""

    async def present(self, record: CompletionRecord) -> None:
        """Present only the canonical summary from an accepted completion record."""
        ...


__all__ = ["CompletionGuard", "CompletionPresenter", "CompletionStore"]
