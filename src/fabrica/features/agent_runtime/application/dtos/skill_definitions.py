"""Canonical application DTOs for validated Agent Skill definitions."""

import json
import re
from dataclasses import dataclass
from hashlib import sha256

from fabrica.features.agent_runtime.application.dtos.tools import MAX_TOOL_CONTENT_TEXT_CHARS

MAX_SKILL_NAME_CHARS = 64
MAX_SKILL_DESCRIPTION_CHARS = 512
MAX_SKILL_INSTRUCTION_CHARS = 20_000
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """Validated, provider-neutral instructions from one ``SKILL.md`` file."""

    name: str
    description: str
    instructions: str
    revision: str
    disabled: bool = False

    def __post_init__(self) -> None:
        _validate_name(self.name)
        _validate_description(self.description)
        _validate_instructions(self.instructions)
        _validate_revision(self.revision)
        if not isinstance(self.disabled, bool):
            msg = "skill disabled flag must be a boolean"
            raise TypeError(msg)
        if len(self.activation_content_json()) > MAX_TOOL_CONTENT_TEXT_CHARS:
            msg = "skill activation content exceeds the structured text-content bound"
            raise ValueError(msg)

    @classmethod
    def from_skill_file_bytes(
        cls,
        *,
        name: str,
        description: str,
        instructions: str,
        skill_file_bytes: bytes,
        disabled: bool = False,
    ) -> SkillDefinition:
        """Create a definition whose revision identifies the exact source bytes."""
        return cls(
            name=name,
            description=description,
            instructions=instructions,
            revision=f"sha256:{sha256(skill_file_bytes).hexdigest()}",
            disabled=disabled,
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
