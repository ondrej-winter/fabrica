"""Digest-bound terminal approval callback for immutable patch plans."""

from dataclasses import dataclass
from typing import TextIO

from fabrica.features.coding_agent_session.adapters.inbound.terminal.command_approval import _read_confirmation
from fabrica.features.coding_agent_session.adapters.inbound.terminal.rendering import write_patch_preview
from fabrica.features.workspace_editing.application.dtos import PatchApprovalDecision, PatchPlan


@dataclass(frozen=True, slots=True)
class TerminalPatchApproval:
    """Return a terminal decision explicitly bound to the rendered plan digest."""

    stdin: TextIO
    stdout: TextIO

    async def decide(self, plan: PatchPlan) -> PatchApprovalDecision:
        """Render the complete bounded approval view and capture one confirmation."""
        write_patch_preview(self.stdout, plan)
        approved = _read_confirmation(self.stdin, self.stdout, prompt="Apply this patch? [y/N] ")
        return PatchApprovalDecision(
            approved=approved,
            plan_digest=plan.plan_digest,
            reason=None if approved else "terminal patch approval was denied",
        )
