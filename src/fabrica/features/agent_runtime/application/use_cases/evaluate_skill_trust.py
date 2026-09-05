"""Use case for revision-bound Version 1 Agent Skill trust evaluation."""

from fabrica.features.agent_runtime.application.dtos import (
    SkillTrustDecisionStatus,
    SkillTrustEvaluationCommand,
    SkillTrustEvaluationResult,
    SkillTrustEvaluationStatus,
)
from fabrica.features.agent_runtime.application.ports import (
    SkillRevisionDefinitionLoader,
    SkillRevisionLoadError,
    SkillTrustLookup,
)


class EvaluateSkillTrust:
    """Apply host allowlist, trust, and safe reread-and-hash revision checks."""

    def __init__(self, trust_lookup: SkillTrustLookup, revision_loader: SkillRevisionDefinitionLoader) -> None:
        self._trust_lookup = trust_lookup
        self._revision_loader = revision_loader

    def evaluate(self, command: SkillTrustEvaluationCommand) -> SkillTrustEvaluationResult:
        """Return a verified definition only when policy and exact revision both match."""
        binding = command.binding
        if command.allowed_skill_ids is not None and command.skill.skill_id not in command.allowed_skill_ids:
            return SkillTrustEvaluationResult(status=SkillTrustEvaluationStatus.NOT_ALLOWED, binding=binding)

        decision = self._trust_lookup.get_decision(binding)
        if decision.binding != binding or decision.status is SkillTrustDecisionStatus.DENIED:
            return SkillTrustEvaluationResult(status=SkillTrustEvaluationStatus.UNTRUSTED, binding=binding)

        try:
            definition = self._revision_loader.load_registered(command.skill)
        except SkillRevisionLoadError:
            return SkillTrustEvaluationResult(status=SkillTrustEvaluationStatus.DEFINITION_UNAVAILABLE, binding=binding)

        if definition.name != command.skill.name or definition.disabled or definition.revision != binding.revision:
            return SkillTrustEvaluationResult(status=SkillTrustEvaluationStatus.REVISION_MISMATCH, binding=binding)
        return SkillTrustEvaluationResult(
            status=SkillTrustEvaluationStatus.APPROVED,
            binding=binding,
            definition=definition,
        )
