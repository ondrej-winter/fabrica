"""Application DTOs for Version 1 Agent Skill registry snapshots."""

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from fabrica.features.agent_runtime.application.dtos.skill_definitions import SkillDefinition
from fabrica.features.agent_runtime.application.dtos.tools import MAX_TOOL_DESCRIPTION_CHARS

MAX_ENABLED_SKILLS = 50
MAX_ADVERTISED_CATALOG_CHARS = MAX_TOOL_DESCRIPTION_CHARS
SKILL_CATALOG_INTRODUCTION = (
    "Activate a matching skill before substantive work; activation loads instructions only.\n\nAvailable skills:\n"
)
_PARTIAL_CATALOG_NOTICE = "- Additional configured skills are not shown; do not guess omitted skills.\n"
_CANONICAL_SKILL_ID_PATTERN = re.compile(r"^(global|workspace):([a-z0-9]+(?:-[a-z0-9]+)*)$")
_MINIMUM_AMBIGUOUS_SKILL_CANDIDATES = 2


class SkillSource(StrEnum):
    """Configured Version 1 skill provider sources."""

    GLOBAL = "global"
    WORKSPACE = "workspace"


class SkillResolutionStatus(StrEnum):
    """Outcomes of resolving a model-supplied skill identifier."""

    FOUND = "found"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class RegisteredSkill:
    """Model-safe metadata for one validated and enabled registered skill."""

    skill_id: str
    source: SkillSource
    definition: SkillDefinition

    def __post_init__(self) -> None:
        match = _CANONICAL_SKILL_ID_PATTERN.fullmatch(self.skill_id)
        if match is None or match.group(1) != self.source.value or match.group(2) != self.definition.name:
            msg = "registered skill ID must match its source and definition name"
            raise ValueError(msg)
        if self.definition.disabled:
            msg = "disabled skill definitions cannot be registered"
            raise ValueError(msg)

    @property
    def name(self) -> str:
        """Return the human-facing skill name."""
        return self.definition.name

    @property
    def description(self) -> str:
        """Return the skill's model-facing description."""
        return self.definition.description

    @property
    def revision(self) -> str:
        """Return the exact-byte revision of the skill definition."""
        return self.definition.revision


@dataclass(frozen=True, slots=True)
class SkillResolution:
    """Immutable result of resolving one normalized skill invocation."""

    status: SkillResolutionStatus
    skill: RegisteredSkill | None = None
    candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status is SkillResolutionStatus.FOUND and self.skill is None:
            msg = "found skill resolution requires a registered skill"
            raise ValueError(msg)
        if self.status is not SkillResolutionStatus.FOUND and self.skill is not None:
            msg = "only found skill resolution may include a registered skill"
            raise ValueError(msg)
        if (
            self.status is SkillResolutionStatus.AMBIGUOUS
            and len(self.candidates) < _MINIMUM_AMBIGUOUS_SKILL_CANDIDATES
        ):
            msg = "ambiguous skill resolution requires at least two candidates"
            raise ValueError(msg)
        if self.status is not SkillResolutionStatus.AMBIGUOUS and self.candidates:
            msg = "only ambiguous skill resolution may include candidates"
            raise ValueError(msg)
        if tuple(sorted(self.candidates)) != self.candidates or len(set(self.candidates)) != len(self.candidates):
            msg = "skill resolution candidates must be unique and sorted"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SkillRegistrySnapshot:
    """Immutable, run-scoped registry metadata captured before model execution."""

    snapshot_id: str
    registry_revision: str
    skills: tuple[RegisteredSkill, ...]

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip():
            msg = "skill registry snapshot ID must not be empty"
            raise ValueError(msg)
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.registry_revision):
            msg = "skill registry revision must be a lowercase sha256 digest"
            raise ValueError(msg)
        if len(self.skills) > MAX_ENABLED_SKILLS:
            msg = "skill registry snapshot exceeds the enabled skill bound"
            raise ValueError(msg)
        if tuple(sorted(self.skills, key=lambda skill: skill.skill_id)) != self.skills:
            msg = "skill registry snapshot skills must be sorted by canonical ID"
            raise ValueError(msg)
        if len({skill.skill_id for skill in self.skills}) != len(self.skills):
            msg = "skill registry snapshot IDs must be unique"
            raise ValueError(msg)

    @classmethod
    def create(cls, *, snapshot_id: str, skills: tuple[RegisteredSkill, ...]) -> SkillRegistrySnapshot:
        """Create a snapshot with a deterministic metadata revision."""
        ordered_skills = tuple(sorted(skills, key=lambda skill: skill.skill_id))
        payload = [
            {
                "description": skill.description,
                "id": skill.skill_id,
                "revision": skill.revision,
                "source": skill.source.value,
            }
            for skill in ordered_skills
        ]
        revision = (
            f"sha256:{sha256(json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()}"
        )
        return cls(snapshot_id=snapshot_id, registry_revision=revision, skills=ordered_skills)

    def resolve(self, invocation: str) -> SkillResolution:
        """Resolve a canonical or unique bare skill invocation within this snapshot."""
        normalized = _normalize_invocation(invocation)
        direct_match = next((skill for skill in self.skills if skill.skill_id == normalized), None)
        if direct_match is not None:
            return SkillResolution(status=SkillResolutionStatus.FOUND, skill=direct_match)

        candidates = tuple(skill for skill in self.skills if skill.name == normalized)
        if len(candidates) == 1:
            return SkillResolution(status=SkillResolutionStatus.FOUND, skill=candidates[0])
        if len(candidates) > 1:
            return SkillResolution(
                status=SkillResolutionStatus.AMBIGUOUS,
                candidates=tuple(skill.skill_id for skill in candidates),
            )
        return SkillResolution(status=SkillResolutionStatus.MISSING)

    def catalog_description(self) -> str:
        """Render deterministic complete catalog entries within the tool-description bound."""
        result = SKILL_CATALOG_INTRODUCTION
        for index, skill in enumerate(self.skills):
            entry = f"- {skill.skill_id} — {skill.description}\n"
            remaining = len(self.skills) - index - 1
            suffix = _PARTIAL_CATALOG_NOTICE if remaining else ""
            if len(result) + len(entry) + len(suffix) > MAX_ADVERTISED_CATALOG_CHARS:
                return (
                    result + _PARTIAL_CATALOG_NOTICE
                    if len(result) + len(_PARTIAL_CATALOG_NOTICE) <= MAX_ADVERTISED_CATALOG_CHARS
                    else result
                )
            result += entry
        return result.rstrip()


def _normalize_invocation(invocation: str) -> str:
    if not isinstance(invocation, str):
        msg = "skill invocation must be a string"
        raise TypeError(msg)
    normalized = invocation.strip().removeprefix("/").casefold()
    if not normalized:
        msg = "skill invocation must not be empty"
        raise ValueError(msg)
    return normalized
