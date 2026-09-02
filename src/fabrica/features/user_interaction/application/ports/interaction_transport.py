"""Outbound port for publishing structured live interaction events."""

from typing import Protocol

from fabrica.features.user_interaction.application.dtos import InteractionPublication


class InteractionTransport(Protocol):
    """Publish a question to the interactive host exactly once per identifier."""

    async def publish(self, publication: InteractionPublication) -> None:
        """Publish one question using its identifier as the idempotency key."""
        ...


__all__ = ["InteractionTransport"]
