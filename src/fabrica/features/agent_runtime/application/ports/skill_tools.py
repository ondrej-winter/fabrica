"""Skill tool preparation port for selected Agent Skill capabilities."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    SkillToolPreparationCommand,
    SkillToolPreparationResult,
)


class SkillToolPreparationError(Exception):
    """Application-safe failure raised when skill tool preparation fails unexpectedly."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.metadata = dict(metadata or {})


class SkillToolPreparer(Protocol):
    """Outbound port for preparing explicitly selected skill-associated tools."""

    def prepare(self, command: SkillToolPreparationCommand) -> SkillToolPreparationResult:
        """Prepare selected skill tool declarations without binding callables."""
        ...
