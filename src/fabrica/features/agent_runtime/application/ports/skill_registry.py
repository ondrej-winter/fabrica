"""Ports for building immutable Agent Skill registry snapshots."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import SkillDefinition, SkillSource


class SkillRegistryProviderError(Exception):
    """Application-safe failure raised when a configured registry provider cannot discover skills."""


class SkillRegistryProvider(Protocol):
    """Outbound port that discovers validated definitions for one Version 1 source."""

    @property
    def source(self) -> SkillSource:
        """Return this provider's configured source identity."""
        ...

    def discover(self) -> tuple[SkillDefinition, ...]:
        """Return currently usable definitions without exposing filesystem paths."""
        ...
