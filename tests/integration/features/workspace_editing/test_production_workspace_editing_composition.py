"""Integration tests for recovery-gated production apply-patch composition."""

from asyncio import run
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

import fabrica.bootstrap.composition.workspace_editing as workspace_editing_composition
from fabrica.features.agent_runtime.application.dtos import RegisteredToolOutcome, ToolDefinition
from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_editing.adapters.inbound.registered_tool import APPLY_PATCH_TOOL_NAME
from fabrica.features.workspace_editing.adapters.outbound.authorization import PatchApprovalDecision
from fabrica.features.workspace_editing.application.dtos import (
    PatchApprovalPreview,
    PatchError,
    PatchPlan,
    WorkspaceMutationStartupGate,
)
from fabrica.features.workspace_editing.application.errors import patch_error

if TYPE_CHECKING:
    from fabrica.features.workspace_editing.application.ports import PatchApprovalRequester


def test_production_composition_exposes_apply_patch_after_clean_startup(tmp_path: Path, monkeypatch) -> None:
    _install_startup_gate(monkeypatch, WorkspaceMutationStartupGate(mutation_enabled=True))

    composition = run(
        workspace_editing_composition.create_production_workspace_editing_composition(
            tmp_path,
            options=_options(),
        )
    )

    assert composition.mutation_gate.mutation_enabled
    assert _tool_names(composition.tools) == (APPLY_PATCH_TOOL_NAME,)


def test_production_composition_keeps_read_only_tools_when_capability_is_unsupported(
    tmp_path: Path,
    monkeypatch,
) -> None:
    error = patch_error("UNSUPPORTED_FILESYSTEM_GUARANTEE", message="no native no-replace support")
    _install_startup_gate(monkeypatch, _disabled_gate(error))
    read_only_tool = _read_only_tool()

    composition = run(
        workspace_editing_composition.create_production_workspace_editing_composition(
            tmp_path,
            options=_options(),
            read_only_tools=(read_only_tool,),
        )
    )

    assert composition.mutation_gate.error is error
    assert _tool_names(composition.tools) == ("read_only",)


def test_production_composition_keeps_read_only_tools_when_recovery_is_required(tmp_path: Path, monkeypatch) -> None:
    error = patch_error(
        "RECOVERY_REQUIRED",
        message="operator recovery required",
        metadata={"journal_digest": "sha256:" + "b" * 64},
    )
    _install_startup_gate(monkeypatch, _disabled_gate(error))
    read_only_tool = _read_only_tool()

    composition = run(
        workspace_editing_composition.create_production_workspace_editing_composition(
            tmp_path,
            options=_options(),
            read_only_tools=(read_only_tool,),
        )
    )

    assert composition.mutation_gate.error is error
    assert _tool_names(composition.tools) == ("read_only",)


def test_production_composition_wires_mandatory_host_approval(tmp_path: Path, monkeypatch) -> None:
    _install_startup_gate(monkeypatch, WorkspaceMutationStartupGate(mutation_enabled=True))
    approval = _Approval(approved=False)
    captured_approval_requesters: list[PatchApprovalRequester] = []

    def capture_use_case(**kwargs: object) -> _FakePatchApplier:
        captured_approval_requesters.append(cast("PatchApprovalRequester", kwargs["approval_requester"]))
        return _FakePatchApplier()

    monkeypatch.setattr(workspace_editing_composition, "ApplyPatch", capture_use_case)
    run(
        workspace_editing_composition.create_production_workspace_editing_composition(
            tmp_path,
            options=workspace_editing_composition.ProductionWorkspaceEditingOptions(
                approval_callback=approval.decide,
            ),
        )
    )

    approval_requester = captured_approval_requesters[0]
    result = run(approval_requester.request_approval(_plan()))

    assert result is not None
    assert result.error is not None
    assert result.error.code == "APPROVAL_DENIED"
    assert approval.calls == 1


def test_production_composition_accepts_digest_bound_host_approval(tmp_path: Path, monkeypatch) -> None:
    _install_startup_gate(monkeypatch, WorkspaceMutationStartupGate(mutation_enabled=True))
    approval = _Approval(approved=True)
    captured_approval_requesters: list[PatchApprovalRequester] = []

    def capture_use_case(**kwargs: object) -> _FakePatchApplier:
        captured_approval_requesters.append(cast("PatchApprovalRequester", kwargs["approval_requester"]))
        return _FakePatchApplier()

    monkeypatch.setattr(workspace_editing_composition, "ApplyPatch", capture_use_case)
    run(
        workspace_editing_composition.create_production_workspace_editing_composition(
            tmp_path,
            options=workspace_editing_composition.ProductionWorkspaceEditingOptions(
                approval_callback=approval.decide,
            ),
        )
    )

    approval_requester = captured_approval_requesters[0]

    assert run(approval_requester.request_approval(_plan())) is None
    assert approval.calls == 1


def _install_startup_gate(monkeypatch, gate: WorkspaceMutationStartupGate) -> None:
    async def recover(_self) -> WorkspaceMutationStartupGate:
        return gate

    monkeypatch.setattr(workspace_editing_composition.RecoverWorkspaceMutation, "recover", recover)


def _disabled_gate(error: PatchError) -> WorkspaceMutationStartupGate:
    return WorkspaceMutationStartupGate(mutation_enabled=False, error=error)


def _options() -> workspace_editing_composition.ProductionWorkspaceEditingOptions:
    approval = _Approval(approved=True)
    return workspace_editing_composition.ProductionWorkspaceEditingOptions(approval_callback=approval.decide)


def _tool_names(tools: tuple[AsyncRegisteredTool, ...]) -> tuple[str, ...]:
    return tuple(tool.definition.name for tool in tools)


def _read_only_tool() -> AsyncRegisteredTool:
    async def handle(*_args: object) -> RegisteredToolOutcome:
        return RegisteredToolOutcome.recoverable_rejection(error_code="READ_ONLY", error_message="read only")

    return AsyncRegisteredTool(
        definition=ToolDefinition(name="read_only", description="Read-only fixture tool."),
        handler=handle,
    )


def _plan() -> PatchPlan:
    return PatchPlan(
        plan_digest="sha256:" + "a" * 64,
        approval_preview=PatchApprovalPreview(text="Add one file."),
    )


@dataclass(slots=True)
class _FakePatchApplier:
    async def apply(self, *_args: object) -> object:
        raise AssertionError


@dataclass(slots=True)
class _Approval:
    approved: bool
    calls: int = field(default=0, init=False)

    async def decide(self, plan: PatchPlan) -> PatchApprovalDecision:
        self.calls += 1
        return PatchApprovalDecision(approved=self.approved, plan_digest=plan.plan_digest)
