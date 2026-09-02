"""Composition helpers for explicit and production workspace-editing tools."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_editing.adapters.inbound.registered_tool import (
    PatchApplier,
    create_apply_patch_registered_tool,
)
from fabrica.features.workspace_editing.adapters.outbound.authorization import (
    InProcessPatchMutationLeaseManager,
    PatchApprovalDecision,
    StaticPatchApprovalRequester,
    WorkspacePatchPolicyEvaluator,
)
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import (
    PosixPatchCommitAdapter,
    PosixPatchJournalAndPreparationAdapter,
    PosixPatchWorkspaceSnapshotAdapter,
    PosixSupervisedPatchCommitAdapter,
    PosixSupervisedPatchMutationAdapter,
    PosixSupervisedPatchPreparationAdapter,
)
from fabrica.features.workspace_editing.application.dtos import PatchLimits, PatchPlan, WorkspaceMutationStartupGate
from fabrica.features.workspace_editing.application.use_cases import ApplyPatch, RecoverWorkspaceMutation

type PatchApprovalCallback = Callable[[PatchPlan], Awaitable[PatchApprovalDecision]]


@dataclass(frozen=True, slots=True)
class ProductionWorkspaceEditingOptions:
    """Explicit host policy for production apply-patch composition."""

    approval_callback: PatchApprovalCallback
    approval_timeout_seconds: float | None = 30.0
    limits: PatchLimits | None = None


@dataclass(frozen=True, slots=True)
class ProductionWorkspaceEditingComposition:
    """Production mutation tool exposure and immutable startup-gate evidence."""

    tools: tuple[AsyncRegisteredTool, ...]
    mutation_gate: WorkspaceMutationStartupGate


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


async def create_production_workspace_editing_composition(
    workspace_root: Path,
    *,
    options: ProductionWorkspaceEditingOptions,
    read_only_tools: tuple[AsyncRegisteredTool, ...] = (),
) -> ProductionWorkspaceEditingComposition:
    """Compose recovery-gated POSIX mutation alongside independent read-only tools.

    Startup verifies actual workspace capabilities and resolves only proven-safe
    interrupted journals. A failed gate leaves the supplied read-only tools
    available and omits ``apply_patch`` with structured error evidence.
    """
    snapshot_reader = PosixPatchWorkspaceSnapshotAdapter(workspace_root)
    journal = PosixPatchJournalAndPreparationAdapter(workspace_root)
    supervisor = PosixSupervisedPatchMutationAdapter(workspace_root)
    gate = await RecoverWorkspaceMutation(
        snapshot_reader=snapshot_reader,
        journal_store=journal,
        recovery_coordinator=PosixPatchCommitAdapter(workspace_root),
    ).recover()
    if not gate.mutation_enabled:
        return ProductionWorkspaceEditingComposition(tools=read_only_tools, mutation_gate=gate)

    use_case = ApplyPatch(
        lease_manager=InProcessPatchMutationLeaseManager(),
        snapshot_reader=snapshot_reader,
        policy_evaluator=WorkspacePatchPolicyEvaluator(),
        approval_requester=StaticPatchApprovalRequester(
            approval_callback=options.approval_callback,
            timeout_seconds=options.approval_timeout_seconds,
        ),
        journal_store=journal,
        preparation_stager=PosixSupervisedPatchPreparationAdapter(supervisor),
        file_stager=PosixSupervisedPatchCommitAdapter(supervisor),
        committer=PosixSupervisedPatchCommitAdapter(supervisor),
    )
    mutation_tool = create_apply_patch_registered_tool(use_case, limits=options.limits)
    return ProductionWorkspaceEditingComposition(tools=(*read_only_tools, mutation_tool), mutation_gate=gate)


__all__ = [
    "ProductionWorkspaceEditingComposition",
    "ProductionWorkspaceEditingOptions",
    "create_apply_patch_registered_tool_adapter",
    "create_production_workspace_editing_composition",
]
