"""Application DTOs for selected Agent Skill tool exposure."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from fabrica.features.agent_runtime.application.dtos.runtime import (
    RuntimeObservation,
    SafeRuntimeMetadataValue,
)
from fabrica.features.agent_runtime.application.dtos.skills import (
    DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS,
    DEFAULT_MAX_SELECTED_SKILLS,
    SelectedSkill,
)
from fabrica.features.agent_runtime.application.dtos.tools import ToolDefinition

DEFAULT_MAX_SELECTED_SKILL_TOOLS = 32
DEFAULT_MAX_SKILL_TOOL_REASON_CHARS = 1_000


class SkillToolExposureStatus(StrEnum):
    """Normalized exposure status for one selected skill-associated capability."""

    REGISTERED = "registered"
    SKIPPED = "skipped"
    DENIED = "denied"
    DUPLICATE = "duplicate"
    INVALID_METADATA = "invalid_metadata"
    UNKNOWN_SELECTION = "unknown_selection"
    SCRIPT_DEFERRED = "script_deferred"


@dataclass(frozen=True, slots=True)
class SelectedSkillToolDeclaration:
    """Application-safe declaration for one selected skill-associated capability."""

    skill_id: str
    status: SkillToolExposureStatus
    tool: ToolDefinition | None = None
    label: str | None = None
    reason: str | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        SelectedSkill(skill_id=self.skill_id)
        if self.label is not None:
            _validate_safe_skill_tool_text(self.label, field_name="label")
        if self.reason is not None:
            _validate_skill_tool_reason(self.reason)
        if self.status is SkillToolExposureStatus.REGISTERED and self.tool is None:
            msg = "registered skill tool declarations require a tool definition"
            raise ValueError(msg)
        if self.status is SkillToolExposureStatus.SCRIPT_DEFERRED and self.tool is not None:
            msg = "script-deferred skill tool declarations must not expose a tool definition"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def display_label(self) -> str:
        """Return a safe human-facing label for diagnostics."""
        if self.label is not None:
            return self.label
        if self.tool is not None:
            return self.tool.name
        return self.skill_id

    @property
    def exposes_model_tool(self) -> bool:
        """Return whether this declaration contributes a model-callable tool."""
        return self.status is SkillToolExposureStatus.REGISTERED and self.tool is not None

    def with_status(
        self,
        status: SkillToolExposureStatus,
        *,
        reason: str | None = None,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> "SelectedSkillToolDeclaration":
        """Return a fail-closed copy with a replacement exposure status."""
        return SelectedSkillToolDeclaration(
            skill_id=self.skill_id,
            status=status,
            tool=self.tool if status is SkillToolExposureStatus.REGISTERED else None,
            label=self.label,
            reason=reason if reason is not None else self.reason,
            metadata=metadata if metadata is not None else self.metadata,
        )


@dataclass(frozen=True, slots=True)
class SkillToolPreparationCommand:
    """Command for preparing tool exposure for explicitly selected Agent Skills."""

    selected_skills: tuple[SelectedSkill, ...] = field(default_factory=tuple)
    requested_tools: tuple[SelectedSkillToolDeclaration, ...] = field(default_factory=tuple)
    max_selected_tools: int = DEFAULT_MAX_SELECTED_SKILL_TOOLS

    def __post_init__(self) -> None:
        if len(self.selected_skills) > DEFAULT_MAX_SELECTED_SKILLS:
            msg = "selected skill count exceeds the configured bound"
            raise ValueError(msg)
        if self.max_selected_tools < 1:
            msg = "max_selected_tools must be at least 1"
            raise ValueError(msg)
        if len(self.requested_tools) > self.max_selected_tools:
            msg = "selected skill tool count exceeds the configured bound"
            raise ValueError(msg)
        object.__setattr__(self, "selected_skills", tuple(self.selected_skills))
        object.__setattr__(self, "requested_tools", tuple(self.requested_tools))

    @property
    def selected_skill_ids(self) -> frozenset[str]:
        """Return selected skill identifiers for fail-closed declaration checks."""
        return frozenset(selection.skill_id for selection in self.selected_skills)


@dataclass(frozen=True, slots=True)
class SkillToolPreparationResult:
    """Normalized application-safe result for selected skill tool exposure."""

    declarations: tuple[SelectedSkillToolDeclaration, ...] = field(default_factory=tuple)
    observations: tuple[RuntimeObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "declarations", tuple(self.declarations))
        object.__setattr__(self, "observations", tuple(self.observations))

    @property
    def tool_definitions(self) -> tuple[ToolDefinition, ...]:
        """Return model-callable definitions for registered declarations only."""
        return tuple(
            declaration.tool
            for declaration in self.declarations
            if declaration.exposes_model_tool and declaration.tool is not None
        )


def _validate_safe_skill_tool_text(value: str, *, field_name: str) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if len(value) > DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS:
        msg = f"{field_name} exceeds the safe skill label bound"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)


def _validate_skill_tool_reason(value: str) -> None:
    if not value:
        msg = "skill tool exposure reason must not be empty"
        raise ValueError(msg)
    if len(value) > DEFAULT_MAX_SKILL_TOOL_REASON_CHARS:
        msg = "skill tool exposure reason exceeds the safe reason bound"
        raise ValueError(msg)
