"""Application-owned ports for workspace-contained command execution."""
# ruff: noqa: D102, EM101, TRY003

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from fabrica.features.workspace_command_execution.application.dtos import (
    CommandExecutionLimits,
    CommandResult,
    PlannedCommand,
    RunCommandsCommand,
    RunCommandsResult,
)


class CommandCancellationSignal(Protocol):
    """Cancellation boundary observed by scheduling and supervision."""

    @property
    def is_cancelled(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class RunCommandsContext:
    """Host-supplied cancellation, deadline, and execution limits."""

    cancellation: CommandCancellationSignal
    limits: CommandExecutionLimits
    deadline_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.deadline_at is not None and self.deadline_at.tzinfo is None:
            raise ValueError("deadline_at must be timezone-aware")


class CommandPermissionDecision(StrEnum):
    """Host permission outcomes for an already planned command."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class CommandWorkspaceResolver(Protocol):
    """Canonical workspace-contained current-directory resolver."""

    def resolve_cwd(self, requested_cwd: str) -> str: ...


class CommandEnvironmentBuilder(Protocol):
    """Host-filtered environment builder."""

    def build_environment(self, requested_overrides: dict[str, str]) -> dict[str, str]: ...


class CommandPermissionEvaluator(Protocol):
    """Host-owned permission evaluator."""

    async def evaluate(self, command: PlannedCommand) -> CommandPermissionDecision: ...


class CommandApprovalResolver(Protocol):
    """Host-owned resolver for permission-required approval."""

    async def resolve(self, command: PlannedCommand) -> bool: ...


class CommandSandboxPreflight(Protocol):
    """Host-owned sandbox admission check."""

    async def allow(self, command: PlannedCommand) -> bool: ...


class CommandSupervisor(Protocol):
    """Owner of process lifecycle, output capture, and cleanup."""

    async def run(self, command: PlannedCommand, context: RunCommandsContext) -> CommandResult: ...


class RunCommandsPort(Protocol):
    """Inbound application contract for a complete workspace command batch."""

    async def run(self, command: RunCommandsCommand, context: RunCommandsContext) -> RunCommandsResult: ...


class CommandProgressReporter(Protocol):
    """Optional host-private transient progress sink."""

    async def report(self, command_index: int, stream: str, chunk: str) -> None: ...
