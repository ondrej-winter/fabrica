"""Host-owned command admission-policy adapters."""

from fabrica.features.workspace_command_execution.adapters.outbound.authorization.adapter import (
    HostCommandApprovalResolver,
    HostCommandPermissionEvaluator,
    HostCommandSandboxPreflight,
)

__all__ = ["HostCommandApprovalResolver", "HostCommandPermissionEvaluator", "HostCommandSandboxPreflight"]
