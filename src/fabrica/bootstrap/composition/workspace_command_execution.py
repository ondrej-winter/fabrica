"""Composition helpers for explicitly policy-governed workspace command tools."""

import sys
from dataclasses import dataclass
from pathlib import Path

from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_command_execution.adapters.inbound.registered_tool import (
    create_run_commands_registered_tool,
)
from fabrica.features.workspace_command_execution.adapters.outbound.posix_filesystem import (
    PosixWorkspaceCommandResolver,
)
from fabrica.features.workspace_command_execution.adapters.outbound.process_supervisor import (
    PosixCommandSupervisor,
    PosixCommandSupervisorSettings,
)
from fabrica.features.workspace_command_execution.application.dtos import CommandExecutionLimits
from fabrica.features.workspace_command_execution.application.ports import (
    CommandApprovalResolver,
    CommandEnvironmentBuilder,
    CommandPermissionEvaluator,
    CommandSandboxPreflight,
    CommandSupervisor,
)
from fabrica.features.workspace_command_execution.application.use_cases import PlanCommands, RunCommands

_SUPPORTED_POSIX_PLATFORMS = frozenset({"darwin", "linux"})


@dataclass(frozen=True, slots=True)
class RunCommandsToolOptions:
    """Explicit host-owned policy and supervision dependencies for run-commands."""

    shell_executable: str
    environment_builder: CommandEnvironmentBuilder
    permission_evaluator: CommandPermissionEvaluator
    approval_resolver: CommandApprovalResolver
    sandbox_preflight: CommandSandboxPreflight
    limits: CommandExecutionLimits | None = None
    supervisor: CommandSupervisor | None = None


def create_run_commands_registered_tool_adapter(
    workspace_root: Path,
    *,
    options: RunCommandsToolOptions,
) -> AsyncRegisteredTool:
    """Create the run-commands tool from explicit host policy and supervision.

    The default supervisor targets macOS and Linux POSIX process groups. Other
    platforms must provide a platform-specific ``supervisor`` explicitly.
    Construction only wires adapters; it does not inspect the workspace, spawn a
    process, evaluate policy, request approval, or call a model.
    """
    resolved_supervisor = options.supervisor or _create_posix_supervisor(workspace_root, options.shell_executable)
    resolved_limits = options.limits or CommandExecutionLimits()
    planner = PlanCommands(
        workspace_resolver=PosixWorkspaceCommandResolver(workspace_root),
        environment_builder=options.environment_builder,
        permission_evaluator=options.permission_evaluator,
        approval_resolver=options.approval_resolver,
        sandbox_preflight=options.sandbox_preflight,
    )
    return create_run_commands_registered_tool(
        RunCommands(planner=planner, supervisor=resolved_supervisor),
        limits=resolved_limits,
    )


def _create_posix_supervisor(workspace_root: Path, shell_executable: str) -> PosixCommandSupervisor:
    if sys.platform not in _SUPPORTED_POSIX_PLATFORMS:
        msg = "default POSIX command supervision is supported only on macOS and Linux; provide a supervisor"
        raise RuntimeError(msg)
    return PosixCommandSupervisor(
        workspace_root=workspace_root,
        settings=PosixCommandSupervisorSettings(shell_executable=shell_executable),
    )


__all__ = ["RunCommandsToolOptions", "create_run_commands_registered_tool_adapter"]
