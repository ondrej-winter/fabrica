"""Skill script policy ports for local agent runtime use cases."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptExecutionCommand,
    SkillScriptExecutionResult,
    SkillScriptMetadata,
)


class SkillScriptMetadataLoadError(Exception):
    """Application-safe failure raised when selected script metadata cannot load."""

    def __init__(
        self,
        message: str,
        *,
        skill_id: str,
        script_id: str,
        category: str,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.skill_id = skill_id
        self.script_id = script_id
        self.category = category
        self.metadata = dict(metadata or {})


class SkillScriptExecutionError(Exception):
    """Application-safe failure raised for unexpected execution adapter errors."""

    def __init__(
        self,
        message: str,
        *,
        skill_id: str,
        script_id: str,
        category: str,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.skill_id = skill_id
        self.script_id = script_id
        self.category = category
        self.metadata = dict(metadata or {})


class SkillScriptApprovalLookup(Protocol):
    """Outbound port for non-interactive approval lookup for one script binding."""

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        """Return the stored approval decision for a selected script binding."""
        ...


class SkillScriptMetadataLoader(Protocol):
    """Outbound port for loading metadata for one explicitly selected script."""

    def load_metadata(self, selection: SelectedSkillScript) -> SkillScriptMetadata:
        """Load read-only metadata for an explicitly selected skill script."""
        ...


class SkillScriptExecutor(Protocol):
    """Outbound port for executing an approved selected skill script."""

    def execute(
        self,
        command: SkillScriptExecutionCommand,
        approved_binding: SkillScriptApprovalBinding,
    ) -> SkillScriptExecutionResult:
        """Execute a selected script whose approval binding already matched policy."""
        ...
