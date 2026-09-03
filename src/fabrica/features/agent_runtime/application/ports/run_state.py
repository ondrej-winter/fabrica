"""Application-owned run lifecycle port for completion-aware agent runs."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos.completion import CompletionRunState


class RunStateMachine(Protocol):
    """Track the local lifecycle state of a completion-aware run."""

    def state_for(self, run_id: str) -> CompletionRunState:
        """Return the current lifecycle state for ``run_id``."""
        ...

    def mark_completed(self, run_id: str) -> None:
        """Record a durably committed ``RUNNING → COMPLETED`` transition."""
        ...


__all__ = ["RunStateMachine"]
