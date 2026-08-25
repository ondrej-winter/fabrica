"""Composition helpers for explicitly supplied workspace-editing tools."""

from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_editing.adapters.inbound.registered_tool import (
    PatchApplier,
    create_apply_patch_registered_tool,
)
from fabrica.features.workspace_editing.application.dtos import PatchLimits


def create_apply_patch_registered_tool_adapter(
    use_case: PatchApplier,
    *,
    limits: PatchLimits | None = None,
) -> AsyncRegisteredTool:
    """Create the model-facing apply-patch tool from injected application dependencies.

    This helper performs no filesystem probing, approval prompting, backend calls,
    or mutation during construction. Production mutation dependencies remain
    explicit and caller supplied until platform capability evidence is complete.
    """
    return create_apply_patch_registered_tool(use_case, limits=limits)


__all__ = ["create_apply_patch_registered_tool_adapter"]
