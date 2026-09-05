"""Canonical application DTOs for validated Agent Skill definitions."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from math import isfinite
from types import MappingProxyType
from typing import cast

from fabrica.features.agent_runtime.application.dtos.tools import MAX_TOOL_CONTENT_TEXT_CHARS

MAX_SKILL_NAME_CHARS = 64
MAX_SKILL_DESCRIPTION_CHARS = 512
MAX_SKILL_INSTRUCTION_CHARS = 20_000
MAX_SKILL_METADATA_NESTING_DEPTH = 8
MAX_SKILL_METADATA_MAPPING_ENTRIES = 100
MAX_SKILL_METADATA_SEQUENCE_ENTRIES = 100
MAX_SKILL_METADATA_STRING_CHARS = 20_000
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

type SkillMetadataValue = (
    str | int | float | bool | tuple[SkillMetadataValue, ...] | Mapping[str, SkillMetadataValue] | None
)


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """Validated, provider-neutral instructions and metadata from one ``SKILL.md`` file."""

    name: str
    description: str
    instructions: str
    revision: str
    disabled: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_name(self.name)
        _validate_description(self.description)
        _validate_instructions(self.instructions)
        _validate_revision(self.revision)
        if not isinstance(self.disabled, bool):
            msg = "skill disabled flag must be a boolean"
            raise TypeError(msg)
        object.__setattr__(self, "metadata", _normalize_skill_metadata(self.metadata))
        if len(self.activation_content_json()) > MAX_TOOL_CONTENT_TEXT_CHARS:
            msg = "skill activation content exceeds the structured text-content bound"
            raise ValueError(msg)

    @classmethod
    def from_skill_file_bytes(  # noqa: PLR0913
        cls,
        *,
        name: str,
        description: str,
        instructions: str,
        skill_file_bytes: bytes,
        disabled: bool = False,
        metadata: Mapping[str, object] | None = None,
    ) -> SkillDefinition:
        """Create a definition whose revision identifies the exact source bytes."""
        return cls(
            name=name,
            description=description,
            instructions=instructions,
            revision=f"sha256:{sha256(skill_file_bytes).hexdigest()}",
            disabled=disabled,
            metadata={} if metadata is None else metadata,
        )

    def activation_content_json(self) -> str:
        """Return the bounded canonical structured content shape for later activation."""
        return json.dumps(
            {
                "success": True,
                "status": "activated",
                "skill": {
                    "name": self.name,
                    "description": self.description,
                    "revision": self.revision,
                    "metadata": _json_serializable_metadata(self.metadata),
                },
                "instructions": self.instructions,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


def _validate_name(value: str) -> None:
    if not isinstance(value, str) or not SKILL_NAME_PATTERN.fullmatch(value):
        msg = "skill name must be lowercase kebab-case"
        raise ValueError(msg)
    if len(value) > MAX_SKILL_NAME_CHARS:
        msg = "skill name exceeds the configured bound"
        raise ValueError(msg)


def _validate_description(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        msg = "skill description must not be empty"
        raise ValueError(msg)
    if value != value.strip():
        msg = "skill description must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if len(value) > MAX_SKILL_DESCRIPTION_CHARS:
        msg = "skill description exceeds the configured bound"
        raise ValueError(msg)


def _validate_instructions(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        msg = "skill instructions must not be empty"
        raise ValueError(msg)
    if len(value) > MAX_SKILL_INSTRUCTION_CHARS:
        msg = "skill instructions exceed the configured bound"
        raise ValueError(msg)


def _validate_revision(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        msg = "skill revision must be a lowercase sha256 digest"
        raise ValueError(msg)


def _normalize_skill_metadata(metadata: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(metadata, Mapping):
        msg = "skill metadata must be a mapping"
        raise TypeError(msg)
    return _normalize_skill_metadata_mapping(metadata, depth=1)


def _normalize_skill_metadata_value(value: object, *, depth: int) -> SkillMetadataValue:
    if depth > MAX_SKILL_METADATA_NESTING_DEPTH:
        msg = "skill metadata exceeds the safe nesting depth"
        raise ValueError(msg)
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            msg = "skill metadata numbers must be finite"
            raise ValueError(msg)
        return value
    if isinstance(value, str):
        if len(value) > MAX_SKILL_METADATA_STRING_CHARS:
            msg = "skill metadata strings exceed the safe string bound"
            raise ValueError(msg)
        return value
    if isinstance(value, Mapping):
        return cast(
            "SkillMetadataValue",
            _normalize_skill_metadata_mapping(cast("Mapping[str, object]", value), depth=depth),
        )
    if isinstance(value, list | tuple):
        if len(value) > MAX_SKILL_METADATA_SEQUENCE_ENTRIES:
            msg = "skill metadata sequences exceed the safe entry bound"
            raise ValueError(msg)
        return tuple(_normalize_skill_metadata_value(item, depth=depth + 1) for item in value)
    msg = "skill metadata must contain JSON-like values"
    raise TypeError(msg)


def _normalize_skill_metadata_mapping(metadata: Mapping[str, object], *, depth: int) -> Mapping[str, object]:
    if len(metadata) > MAX_SKILL_METADATA_MAPPING_ENTRIES:
        msg = "skill metadata mappings exceed the safe entry bound"
        raise ValueError(msg)
    normalized: dict[str, SkillMetadataValue] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            msg = "skill metadata keys must be strings"
            raise TypeError(msg)
        if len(key) > MAX_SKILL_METADATA_STRING_CHARS:
            msg = "skill metadata keys exceed the safe string bound"
            raise ValueError(msg)
        normalized[key] = _normalize_skill_metadata_value(value, depth=depth + 1)
    return MappingProxyType(normalized)


def _json_serializable_metadata(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _json_serializable_metadata(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_serializable_metadata(item) for item in value]
    return value
