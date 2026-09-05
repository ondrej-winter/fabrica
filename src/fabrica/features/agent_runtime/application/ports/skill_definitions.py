"""Port for loading canonical validated Agent Skill definitions."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import SafeRuntimeMetadataValue, SelectedSkill, SkillDefinition


class SkillDefinitionLoadError(Exception):
    """Application-safe failure raised when a skill definition cannot load."""

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


class SkillDefinitionLoader(Protocol):
    """Outbound port for loading one validated Agent Skill definition."""

    def load(self, selection: SelectedSkill) -> SkillDefinition:
        """Load and validate one selected skill definition."""
        ...
