"""CLI approval lookup adapters for selected skill script execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fabrica.features.agent_runtime.application.dtos import (
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
)

if TYPE_CHECKING:
    from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import CliScriptExecuteCommand


@dataclass(frozen=True, slots=True)
class MetadataBoundCliApprovalLookup:
    """Approve only a selected script binding matching CLI-supplied metadata."""

    command: CliScriptExecuteCommand

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        """Return approval when the current binding exactly matches CLI metadata."""
        expected = SkillScriptApprovalBinding(
            skill_id=self.command.skill_id,
            script_id=self.command.script_id,
            script_type=self.command.approval_options.script_type,
            suffix=self.command.approval_options.suffix,
            byte_size=self.command.approval_options.byte_size,
            content_digest=self.command.approval_options.content_digest,
        )
        if binding == expected:
            return SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.APPROVED, binding=binding)
        return SkillScriptApprovalDecision(
            status=SkillScriptApprovalStatus.DENIED,
            binding=binding,
            reason="CLI approval metadata did not match selected script metadata",
        )


__all__ = ["MetadataBoundCliApprovalLookup"]
