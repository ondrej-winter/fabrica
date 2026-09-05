"""Ports for revision-bound Version 1 Agent Skill trust and integrity checks."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredSkill,
    SkillDefinition,
    SkillTrustBinding,
    SkillTrustDecision,
    SkillTrustEvaluationCommand,
    SkillTrustEvaluationResult,
)


class SkillRevisionLoadError(Exception):
    """Application-safe failure when an exact snapshot skill definition cannot reload."""


class SkillRevisionDefinitionLoader(Protocol):
    """Outbound port that safely rereads a definition from its configured source."""

    def load_registered(self, skill: RegisteredSkill) -> SkillDefinition:
        """Return the current validated definition without exposing source paths."""
        ...


class SkillTrustLookup(Protocol):
    """Outbound port for host-owned revision-bound skill trust decisions."""

    def get_decision(self, binding: SkillTrustBinding) -> SkillTrustDecision:
        """Return the trust decision for one exact workspace, run, skill, and revision."""
        ...


class SkillTrustEvaluator(Protocol):
    """Evaluate revision-bound trust before an application activation commit."""

    def evaluate(self, command: SkillTrustEvaluationCommand) -> SkillTrustEvaluationResult:
        """Return a privacy-safe pre-activation evaluation result."""
        ...
