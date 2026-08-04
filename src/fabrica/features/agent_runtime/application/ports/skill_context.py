"""Skill context loading port for local agent runtime use cases."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillContext,
    LoadedSkillResourceContext,
    SafeRuntimeMetadataValue,
    SelectedSkill,
    SelectedSkillResource,
)


class SkillContextLoadError(Exception):
    """Application-safe failure raised when selected skill context cannot load."""

    def __init__(
        self,
        message: str,
        *,
        skill_id: str,
        category: str,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.skill_id = skill_id
        self.category = category
        self.metadata = dict(metadata or {})


class SkillContextLoader(Protocol):
    """Outbound port for loading one explicitly selected Agent Skill."""

    def load(self, selection: SelectedSkill) -> LoadedSkillContext:
        """Load markdown context for an explicitly selected skill."""
        ...


class SkillResourceContextLoader(Protocol):
    """Outbound port for loading one explicitly selected Agent Skill resource."""

    def load(self, selection: SelectedSkillResource) -> LoadedSkillResourceContext:
        """Load text context for an explicitly selected skill resource."""
        ...
