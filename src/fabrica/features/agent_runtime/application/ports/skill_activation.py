"""Ports for privacy-safe Agent Skill activation audit recording."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos.skill_activation import SkillActivationAuditEvent


class SkillActivationAuditRecorder(Protocol):
    """Record committed activation metadata without caller-supplied arguments or instructions."""

    def record(self, event: SkillActivationAuditEvent) -> None:
        """Persist or publish one completed activation audit event."""
        ...
