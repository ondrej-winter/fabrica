"""Metadata-bound approval lookup adapter for selected skill script execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fabrica.features.agent_runtime.application.dtos import (
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
)

if TYPE_CHECKING:
    from fabrica.features.agent_runtime.application.dtos import SkillScriptApprovalBinding


@dataclass(frozen=True, slots=True)
class MetadataBoundApprovalLookup:
    """Approve only a selected script binding matching an expected metadata binding."""

    expected_binding: SkillScriptApprovalBinding

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        """Return approval when the script metadata exactly matches the expected binding."""
        if binding == self.expected_binding:
            return SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.APPROVED, binding=binding)
        return SkillScriptApprovalDecision(
            status=SkillScriptApprovalStatus.DENIED,
            binding=binding,
            reason="approval metadata did not match selected script metadata",
        )


__all__ = ["MetadataBoundApprovalLookup"]
