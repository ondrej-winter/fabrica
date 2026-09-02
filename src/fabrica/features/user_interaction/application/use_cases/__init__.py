"""Application use cases for live user interactions."""

from fabrica.features.user_interaction.application.use_cases.manage_interaction import (
    InMemoryInteractionManager,
    InteractionManagerError,
)

__all__ = ["InMemoryInteractionManager", "InteractionManagerError"]
