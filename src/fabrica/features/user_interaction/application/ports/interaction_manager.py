"""Published application API for one live user-interaction owner."""

from typing import Protocol

from fabrica.features.user_interaction.application.dtos import (
    AnswerSubmission,
    InteractionOwner,
    InteractionQuestion,
    InteractionResult,
)


class InteractionManager(Protocol):
    """Create, resolve, and release live interactions for opaque owners."""

    async def ask(self, owner: InteractionOwner, question: InteractionQuestion) -> InteractionResult:
        """Publish one question and wait until it receives a terminal resolution."""
        ...

    async def submit_answer(self, owner: InteractionOwner, submission: AnswerSubmission) -> InteractionResult:
        """Resolve or replay one answer submission for its authorized owner."""
        ...

    async def cancel(self, owner: InteractionOwner, question_id: str) -> InteractionResult:
        """Cancel or replay one interaction for its authorized owner."""
        ...

    async def cancel_owner(self, owner: InteractionOwner) -> None:
        """Cancel every pending interaction owned by one live run/session."""
        ...

    async def release_owner(self, owner: InteractionOwner) -> None:
        """Cancel pending work and remove all retained records for one owner."""
        ...


__all__ = ["InteractionManager"]
