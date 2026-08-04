"""Application DTOs for selected Agent Skills runtime context."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from fabrica.features.agent_runtime.application.dtos.runtime import (
    MAX_CONTEXT_TEXT_CHARS,
    SafeRuntimeMetadataValue,
)

DEFAULT_MAX_SELECTED_SKILLS = 8
DEFAULT_MAX_SKILL_CONTEXT_CHARS = 8_000
DEFAULT_MAX_TOTAL_SKILL_CONTEXT_CHARS = 16_000
DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS = 120
DEFAULT_MAX_SELECTED_SKILL_RESOURCES = 8
DEFAULT_MAX_SKILL_RESOURCE_CONTEXT_CHARS = 8_000
DEFAULT_MAX_TOTAL_SKILL_RESOURCE_CONTEXT_CHARS = 16_000
DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS = 160

SAFE_SKILL_LABEL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ._-/")


@dataclass(frozen=True, slots=True)
class SkillContextBounds:
    """Bounds for selected Agent Skills context loaded into one runtime run."""

    max_selected_skills: int = DEFAULT_MAX_SELECTED_SKILLS
    max_chars_per_skill: int = DEFAULT_MAX_SKILL_CONTEXT_CHARS
    max_total_chars: int = DEFAULT_MAX_TOTAL_SKILL_CONTEXT_CHARS
    max_label_chars: int = DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS

    def __post_init__(self) -> None:
        if self.max_selected_skills < 1:
            msg = "max_selected_skills must be at least 1"
            raise ValueError(msg)
        if self.max_chars_per_skill < 1:
            msg = "max_chars_per_skill must be at least 1"
            raise ValueError(msg)
        if self.max_chars_per_skill > MAX_CONTEXT_TEXT_CHARS:
            msg = "max_chars_per_skill exceeds the local runtime context block bound"
            raise ValueError(msg)
        if self.max_total_chars < 1:
            msg = "max_total_chars must be at least 1"
            raise ValueError(msg)
        if self.max_label_chars < 1:
            msg = "max_label_chars must be at least 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SkillResourceContextBounds:
    """Bounds for selected Agent Skill resources loaded into one runtime run."""

    max_selected_resources: int = DEFAULT_MAX_SELECTED_SKILL_RESOURCES
    max_chars_per_resource: int = DEFAULT_MAX_SKILL_RESOURCE_CONTEXT_CHARS
    max_total_chars: int = DEFAULT_MAX_TOTAL_SKILL_RESOURCE_CONTEXT_CHARS
    max_label_chars: int = DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS

    def __post_init__(self) -> None:
        if self.max_selected_resources < 1:
            msg = "max_selected_resources must be at least 1"
            raise ValueError(msg)
        if self.max_chars_per_resource < 1:
            msg = "max_chars_per_resource must be at least 1"
            raise ValueError(msg)
        if self.max_chars_per_resource > MAX_CONTEXT_TEXT_CHARS:
            msg = "max_chars_per_resource exceeds the local runtime context block bound"
            raise ValueError(msg)
        if self.max_total_chars < 1:
            msg = "max_total_chars must be at least 1"
            raise ValueError(msg)
        if self.max_label_chars < 1:
            msg = "max_label_chars must be at least 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SelectedSkill:
    """Path-free reference to an explicitly selected local Agent Skill."""

    skill_id: str
    label: str | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_safe_skill_text(self.skill_id, field_name="skill_id")
        if self.label is not None:
            _validate_safe_skill_text(self.label, field_name="label")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def display_label(self) -> str:
        """Return the safe human-facing label for this selected skill."""
        return self.label or self.skill_id


@dataclass(frozen=True, slots=True)
class SelectedSkillResource:
    """Path-free reference to an explicitly selected Agent Skill resource."""

    skill_id: str
    resource_id: str
    label: str | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_safe_skill_text(self.skill_id, field_name="skill_id")
        _validate_safe_resource_text(self.resource_id, field_name="resource_id")
        if self.label is not None:
            _validate_safe_resource_text(self.label, field_name="label")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def display_label(self) -> str:
        """Return the safe human-facing label for this selected resource."""
        return self.label or f"{self.skill_id}/{self.resource_id}"


@dataclass(frozen=True, slots=True)
class LoadedSkillContext:
    """Loaded markdown context for one selected Agent Skill."""

    skill_id: str
    markdown: str
    label: str | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_safe_skill_text(self.skill_id, field_name="skill_id")
        if self.label is not None:
            _validate_safe_skill_text(self.label, field_name="label")
        if not self.markdown.strip():
            msg = "skill markdown must not be empty"
            raise ValueError(msg)
        if len(self.markdown) > MAX_CONTEXT_TEXT_CHARS:
            msg = "skill markdown exceeds the local runtime context block bound"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def display_label(self) -> str:
        """Return the safe human-facing label for this loaded skill."""
        return self.label or self.skill_id


@dataclass(frozen=True, slots=True)
class LoadedSkillResourceContext:
    """Loaded text context for one explicitly selected Agent Skill resource."""

    skill_id: str
    resource_id: str
    text: str
    label: str | None = None
    media_type: str = "text/plain"
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_safe_skill_text(self.skill_id, field_name="skill_id")
        _validate_safe_resource_text(self.resource_id, field_name="resource_id")
        if self.label is not None:
            _validate_safe_resource_text(self.label, field_name="label")
        if not self.text.strip():
            msg = "skill resource text must not be empty"
            raise ValueError(msg)
        if len(self.text) > MAX_CONTEXT_TEXT_CHARS:
            msg = "skill resource text exceeds the local runtime context block bound"
            raise ValueError(msg)
        _validate_safe_resource_text(self.media_type, field_name="media_type")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def display_label(self) -> str:
        """Return the safe human-facing label for this loaded resource."""
        return self.label or f"{self.skill_id}/{self.resource_id}"


def _validate_safe_skill_text(value: str, *, field_name: str) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if len(value) > DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS:
        msg = f"{field_name} exceeds the safe skill label bound"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if any(character not in SAFE_SKILL_LABEL_CHARS for character in value):
        msg = f"{field_name} contains unsupported characters"
        raise ValueError(msg)


def _validate_safe_resource_text(value: str, *, field_name: str) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if len(value) > DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS:
        msg = f"{field_name} exceeds the safe skill resource label bound"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if value.startswith("/") or "//" in value:
        msg = f"{field_name} must be a relative resource identifier"
        raise ValueError(msg)
    if any(part in {"", ".", ".."} for part in value.split("/")):
        msg = f"{field_name} must not contain traversal segments"
        raise ValueError(msg)
    if any(character not in SAFE_SKILL_LABEL_CHARS for character in value):
        msg = f"{field_name} contains unsupported characters"
        raise ValueError(msg)
