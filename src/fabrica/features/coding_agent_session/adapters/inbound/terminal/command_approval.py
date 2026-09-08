"""Terminal approval adapter for one resolved workspace command."""

from dataclasses import dataclass
from typing import TextIO

from fabrica.features.coding_agent_session.adapters.inbound.terminal.rendering import write_command_preview
from fabrica.features.workspace_command_execution.application.dtos import PlannedCommand


@dataclass(frozen=True, slots=True)
class TerminalCommandApprovalResolver:
    """Grant command permission only after one explicit terminal confirmation."""

    stdin: TextIO
    stdout: TextIO

    async def resolve(self, command: PlannedCommand) -> bool:
        """Render and approve only the supplied resolved command."""
        write_command_preview(self.stdout, command)
        return _read_confirmation(self.stdin, self.stdout, prompt="Run this command? [y/N] ")


def _read_confirmation(stdin: TextIO, stdout: TextIO, *, prompt: str) -> bool:
    stdout.write(prompt)
    stdout.flush()
    try:
        answer = stdin.readline()
    except KeyboardInterrupt:
        return False
    return answer.strip().casefold() in {"y", "yes"}
