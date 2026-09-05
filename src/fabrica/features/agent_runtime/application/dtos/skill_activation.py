"""Application DTOs for run-scoped Version 1 Agent Skill activation."""

from dataclasses import dataclass, field
from enum import StrEnum

from fabrica.features.agent_runtime.application.dtos.skill_registry import (
    SkillRegistrySnapshot,
    SkillSource,
)

DEFAULT_SKILL_LOAD_TIMEOUT_SECONDS = 15.0


class SkillActivationReason(StrEnum):
    """Trusted caller origins for a skill activation request."""

    MODEL_SELECTED = "model_selected"
    USER_SLASH_COMMAND = "user_slash_command"
    HOST_FORCED = "host_forced"


class SkillActivationStatus(StrEnum):
    """Successful or recoverable outcomes of one skill activation attempt."""

    ACTIVATED = "activated"
    ALREADY_ACTIVE = "already_active"
    INVALID_INPUT = "invalid_input"
    SKILL_NOT_FOUND = "skill_not_found"
    AMBIGUOUS_SKILL = "ambiguous_skill"
    SKILL_NOT_ALLOWED = "skill_not_allowed"
    SKILL_UNTRUSTED = "skill_untrusted"
    INVALID_SKILL_DEFINITION = "invalid_skill_definition"
    SKILL_LOAD_TIMEOUT = "skill_load_timeout"
    SKILL_LOAD_CANCELLED = "skill_load_cancelled"
    INTERNAL_SKILL_ERROR = "internal_skill_error"


@dataclass(frozen=True, slots=True)
class ActiveSkill:
    """One revision-pinned instruction set active for a single registry snapshot."""

    skill_id: str
    instruction_revision: str
    instructions: str
    activation_order: int
    registry_snapshot_id: str

    def __post_init__(self) -> None:
        if not self.skill_id:
            msg = "active skill ID must not be empty"
            raise ValueError(msg)
        if not self.instruction_revision.startswith("sha256:"):
            msg = "active skill revision must be a sha256 digest"
            raise ValueError(msg)
        if not self.instructions:
            msg = "active skill instructions must not be empty"
            raise ValueError(msg)
        if self.activation_order < 0:
            msg = "active skill activation order must not be negative"
            raise ValueError(msg)
        if not self.registry_snapshot_id:
            msg = "active skill registry snapshot ID must not be empty"
            raise ValueError(msg)


@dataclass(slots=True)
class ActiveSkillSet:
    """Application-owned, ordered active state for one run and registry snapshot."""

    run_id: str
    registry_snapshot_id: str
    _skills: list[ActiveSkill] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.run_id:
            msg = "active skill set run ID must not be empty"
            raise ValueError(msg)
        if not self.registry_snapshot_id:
            msg = "active skill set registry snapshot ID must not be empty"
            raise ValueError(msg)

    @property
    def skills(self) -> tuple[ActiveSkill, ...]:
        """Return active skills in their immutable activation order."""
        return tuple(self._skills)

    def contains(self, *, skill_id: str, revision: str) -> bool:
        """Return whether this exact skill revision is already active."""
        return any(skill.skill_id == skill_id and skill.instruction_revision == revision for skill in self._skills)

    def register(self, *, skill_id: str, revision: str, instructions: str) -> ActiveSkill:
        """Atomically retain a new revision without replacing existing active instructions."""
        if self.contains(skill_id=skill_id, revision=revision):
            msg = "an already active skill revision must not be registered again"
            raise ValueError(msg)
        if any(skill.skill_id == skill_id for skill in self._skills):
            msg = "an active skill cannot be silently replaced with another revision"
            raise ValueError(msg)
        active_skill = ActiveSkill(
            skill_id=skill_id,
            instruction_revision=revision,
            instructions=instructions,
            activation_order=len(self._skills),
            registry_snapshot_id=self.registry_snapshot_id,
        )
        self._skills.append(active_skill)
        return active_skill


@dataclass(frozen=True, slots=True)
class SkillActivationCommand:
    """Run-scoped request to activate one skill from an immutable registry snapshot."""

    workspace_identity: str
    run_id: str
    snapshot: SkillRegistrySnapshot
    skill: str
    args: str | None = None
    allowed_skill_ids: frozenset[str] | None = None
    reason: SkillActivationReason = SkillActivationReason.MODEL_SELECTED

    def __post_init__(self) -> None:
        if not self.workspace_identity:
            msg = "workspace identity must not be empty"
            raise ValueError(msg)
        if not self.run_id:
            msg = "run ID must not be empty"
            raise ValueError(msg)
        if not isinstance(self.skill, str):
            msg = "skill invocation must be a string"
            raise TypeError(msg)
        if self.args is not None and not isinstance(self.args, str):
            msg = "skill arguments must be a string or null"
            raise TypeError(msg)
        if self.allowed_skill_ids is not None:
            object.__setattr__(self, "allowed_skill_ids", frozenset(self.allowed_skill_ids))


@dataclass(frozen=True, slots=True)
class SkillActivationAuditEvent:
    """Privacy-safe audit data emitted only after an activation is committed."""

    skill_id: str
    revision: str
    source: SkillSource
    reason: SkillActivationReason
    run_id: str
    registry_snapshot_id: str


@dataclass(frozen=True, slots=True)
class SkillActivationResult:
    """Application result that keeps invocation arguments separate from instructions."""

    status: SkillActivationStatus
    args: str | None
    active_skill: ActiveSkill | None = None
    description: str | None = None
    source: SkillSource | None = None
    candidates: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return whether activation completed or found an idempotent prior activation."""
        return self.status in {SkillActivationStatus.ACTIVATED, SkillActivationStatus.ALREADY_ACTIVE}
