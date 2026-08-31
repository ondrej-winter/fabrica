"""Application errors used while preparing commands for execution."""

from dataclasses import dataclass

from fabrica.features.workspace_command_execution.application.dtos import CommandErrorCode


@dataclass(frozen=True, slots=True)
class CommandPlanningError(Exception):
    """A host-safe, command-scoped planning failure."""

    code: CommandErrorCode
    message: str

    def __str__(self) -> str:
        """Return the host-safe failure message."""
        return self.message
