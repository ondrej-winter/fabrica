"""Terminal acknowledgement adapter for one displayed stale-context replan."""

from dataclasses import dataclass
from typing import TextIO

from fabrica.features.agent_session.application import ReplanSafetyGate
from fabrica.features.coding_agent_session.adapters.inbound.terminal.command_approval import _read_confirmation
from fabrica.features.coding_agent_session.adapters.inbound.terminal.rendering import write_stale_context_replan


@dataclass(frozen=True, slots=True)
class TerminalStaleContextReplanAcknowledgement:
    """Capture acknowledgement for a displayed refreshed plan without approving actions."""

    stdin: TextIO
    stdout: TextIO
    gate: ReplanSafetyGate

    def acknowledge(self, *, summary: str, plan_digest: str) -> bool:
        """Display one digest-bound replan and record an explicit terminal response."""
        if not summary.strip():
            msg = "refreshed plan summary must not be empty"
            raise ValueError(msg)
        self.gate.display_refreshed_plan(plan_digest)
        write_stale_context_replan(self.stdout, summary=summary, plan_digest=plan_digest)
        acknowledged = _read_confirmation(self.stdin, self.stdout, prompt="Acknowledge this refreshed plan? [y/N] ")
        self.gate.acknowledge_displayed_plan(acknowledged=acknowledged)
        return acknowledged
