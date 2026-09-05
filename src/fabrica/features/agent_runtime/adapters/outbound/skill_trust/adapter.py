"""Adapters for exact skill-trust bindings and safe reread-and-hash verification."""

from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredSkill,
    SelectedSkill,
    SkillDefinition,
    SkillSource,
    SkillTrustBinding,
    SkillTrustDecision,
    SkillTrustDecisionStatus,
)
from fabrica.features.agent_runtime.application.ports import (
    SkillDefinitionLoader,
    SkillDefinitionLoadError,
    SkillRevisionLoadError,
)


@dataclass(frozen=True, slots=True)
class MetadataBoundSkillTrustLookup:
    """Return a configured decision only for its exact workspace/run/revision binding."""

    expected_binding: SkillTrustBinding
    approved_status: SkillTrustDecisionStatus = SkillTrustDecisionStatus.APPROVED_FOR_RUN

    def __post_init__(self) -> None:
        if self.approved_status is SkillTrustDecisionStatus.DENIED:
            msg = "metadata-bound skill trust lookup requires a non-denied configured status"
            raise ValueError(msg)

    def get_decision(self, binding: SkillTrustBinding) -> SkillTrustDecision:
        """Return denial unless all approval-binding fields exactly match."""
        return SkillTrustDecision(
            status=self.approved_status if binding == self.expected_binding else SkillTrustDecisionStatus.DENIED,
            binding=binding,
        )


@dataclass(frozen=True, slots=True)
class SourceMappedSkillRevisionDefinitionLoader:
    """Safely reread canonical definitions through the loader configured for each source."""

    loaders_by_source: Mapping[SkillSource, SkillDefinitionLoader]

    def load_registered(self, skill: RegisteredSkill) -> SkillDefinition:
        """Reread and validate the source definition selected by snapshot provenance."""
        try:
            loader = self.loaders_by_source[skill.source]
        except KeyError as err:
            msg = "configured skill source definition loader is unavailable"
            raise SkillRevisionLoadError(msg) from err
        try:
            return loader.load(SelectedSkill(skill_id=skill.name))
        except SkillDefinitionLoadError as err:
            msg = "configured skill definition could not be reread"
            raise SkillRevisionLoadError(msg) from err
