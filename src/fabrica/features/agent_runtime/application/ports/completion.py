"""Application-owned completion persistence and presentation ports."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos.completion import (
    CompletionCommitResult,
    CompletionErrorCode,
    CompletionRecord,
)
from fabrica.features.agent_runtime.application.dtos.tools import ToolCancellationSignal


class CompletionGuardRejectionError(Exception):
    """Safe policy rejection returned by a host-owned completion guard."""

    def __init__(self, code: CompletionErrorCode, message: str) -> None:
        super().__init__(message)
        if code not in {
            CompletionErrorCode.COMPLETION_GUARD_FAILED,
            CompletionErrorCode.VERIFICATION_REQUIREMENT_NOT_MET,
        }:
            msg = "completion guard rejection code is unsupported"
            raise ValueError(msg)
        self.code = code


class CompletionGuard(Protocol):
    """Host-owned policy that may block a proposed terminal completion."""

    async def evaluate(self, record: CompletionRecord) -> None:
        """Allow completion or raise a safe, stable policy rejection."""
        ...


class CompletionStore(Protocol):
    """Atomically persists terminal records with their run-state transition."""

    async def commit_completion(
        self,
        run_id: str,
        record: CompletionRecord,
        cancellation: ToolCancellationSignal,
    ) -> CompletionCommitResult:
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


__all__ = ["CompletionGuard", "CompletionGuardRejectionError", "CompletionPresenter", "CompletionStore"]
