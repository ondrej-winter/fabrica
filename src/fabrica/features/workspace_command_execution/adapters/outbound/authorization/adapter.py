"""Thin adapters around explicit host-owned command-admission callbacks."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fabrica.features.workspace_command_execution.application.dtos import PlannedCommand
from fabrica.features.workspace_command_execution.application.ports import CommandPermissionDecision

type ApprovalCallback = Callable[[PlannedCommand], Awaitable[bool]]
type PermissionCallback = Callable[[PlannedCommand], Awaitable[CommandPermissionDecision]]
type SandboxCallback = Callable[[PlannedCommand], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class HostCommandPermissionEvaluator:
    """Delegate permission decisions to the host's explicit policy callback."""

    evaluate_callback: PermissionCallback

    async def evaluate(self, command: PlannedCommand) -> CommandPermissionDecision:
        """Evaluate one already-resolved command."""
        return await self.evaluate_callback(command)


@dataclass(frozen=True, slots=True)
class HostCommandApprovalResolver:
    """Delegate approval-required decisions to the host's explicit resolver."""

    resolve_callback: ApprovalCallback

    async def resolve(self, command: PlannedCommand) -> bool:
        """Resolve host approval for one command without process-supervisor UI."""
        return await self.resolve_callback(command)


@dataclass(frozen=True, slots=True)
class HostCommandSandboxPreflight:
    """Delegate sandbox admission to the host's explicit policy callback."""

    allow_callback: SandboxCallback

    async def allow(self, command: PlannedCommand) -> bool:
        """Return whether the host admits this command to its sandbox."""
        return await self.allow_callback(command)
