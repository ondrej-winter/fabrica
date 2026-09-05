"""Application DTOs for revision-bound Version 1 Agent Skill trust decisions."""

import re
from dataclasses import dataclass
from enum import StrEnum

from fabrica.features.agent_runtime.application.dtos.skill_definitions import SkillDefinition
from fabrica.features.agent_runtime.application.dtos.skill_registry import RegisteredSkill, SkillSource

_CANONICAL_SKILL_ID_PATTERN = re.compile(r"^(global|workspace):[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256_REVISION_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_CONTEXT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class SkillTrustDecisionStatus(StrEnum):
    """Host-owned trust outcomes for one exact skill binding."""

    TRUSTED = "trusted"
    APPROVED_FOR_RUN = "approved_for_run"
    DENIED = "denied"


class SkillTrustEvaluationStatus(StrEnum):
    """Application outcomes for trust and revision-integrity evaluation."""

    APPROVED = "approved"
    NOT_ALLOWED = "not_allowed"
    UNTRUSTED = "untrusted"
    REVISION_MISMATCH = "revision_mismatch"
    DEFINITION_UNAVAILABLE = "definition_unavailable"


@dataclass(frozen=True, slots=True)
class SkillTrustBinding:
    """Exact identity to which a host trust decision is bound."""

    workspace_identity: str
    run_id: str
    skill_id: str
    source: SkillSource
    revision: str

    def __post_init__(self) -> None:
        _validate_context_identity(self.workspace_identity, field_name="workspace_identity")
        _validate_context_identity(self.run_id, field_name="run_id")
        match = _CANONICAL_SKILL_ID_PATTERN.fullmatch(self.skill_id)
        if match is None or match.group(1) != self.source.value:
            msg = "skill trust binding ID must match its source"
            raise ValueError(msg)
        if _SHA256_REVISION_PATTERN.fullmatch(self.revision) is None:
            msg = "skill trust binding revision must be a lowercase sha256 digest"
            raise ValueError(msg)

    @classmethod
    def from_registered_skill(
        cls,
        *,
        workspace_identity: str,
        run_id: str,
        skill: RegisteredSkill,
    ) -> SkillTrustBinding:
        """Create the exact host-policy binding for one snapshot skill."""
        return cls(
            workspace_identity=workspace_identity,
            run_id=run_id,
            skill_id=skill.skill_id,
            source=skill.source,
            revision=skill.revision,
        )


@dataclass(frozen=True, slots=True)
class SkillTrustDecision:
    """Host trust decision that must echo the exact requested binding."""

    status: SkillTrustDecisionStatus
    binding: SkillTrustBinding


@dataclass(frozen=True, slots=True)
class SkillTrustEvaluationCommand:
    """Host context and snapshot entry submitted for pre-activation evaluation."""

    workspace_identity: str
    run_id: str
    skill: RegisteredSkill
    allowed_skill_ids: frozenset[str] | None = None

    def __post_init__(self) -> None:
        _validate_context_identity(self.workspace_identity, field_name="workspace_identity")
        _validate_context_identity(self.run_id, field_name="run_id")
        if self.allowed_skill_ids is not None:
            normalized_ids = frozenset(self.allowed_skill_ids)
            for skill_id in normalized_ids:
                if _CANONICAL_SKILL_ID_PATTERN.fullmatch(skill_id) is None:
                    msg = "allowed skill IDs must be canonical Version 1 skill IDs"
                    raise ValueError(msg)
            object.__setattr__(self, "allowed_skill_ids", normalized_ids)

    @property
    def binding(self) -> SkillTrustBinding:
        """Return the revision-bound trust identity for this request."""
        return SkillTrustBinding.from_registered_skill(
            workspace_identity=self.workspace_identity,
            run_id=self.run_id,
            skill=self.skill,
        )


@dataclass(frozen=True, slots=True)
class SkillTrustEvaluationResult:
    """Privacy-safe outcome of pre-activation trust and integrity evaluation."""

    status: SkillTrustEvaluationStatus
    binding: SkillTrustBinding
    definition: SkillDefinition | None = None

    def __post_init__(self) -> None:
        if self.status is SkillTrustEvaluationStatus.APPROVED and self.definition is None:
            msg = "approved skill trust evaluation requires a verified definition"
            raise ValueError(msg)
        if self.status is not SkillTrustEvaluationStatus.APPROVED and self.definition is not None:
            msg = "only approved skill trust evaluation may include a definition"
            raise ValueError(msg)

    @property
    def approved(self) -> bool:
        """Return whether activation may consume the verified definition."""
        return self.status is SkillTrustEvaluationStatus.APPROVED


def _validate_context_identity(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or _SAFE_CONTEXT_ID_PATTERN.fullmatch(value) is None:
        msg = f"{field_name} must be a safe non-empty context identifier"
        raise ValueError(msg)
