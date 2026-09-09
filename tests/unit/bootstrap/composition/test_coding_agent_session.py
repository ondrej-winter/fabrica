"""Tests for workspace-scoped coding-agent session composition."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import fabrica.bootstrap.composition.coding_agent_session as composition
from fabrica.bootstrap.composition.workspace_command_execution import RunCommandsToolOptions
from fabrica.bootstrap.composition.workspace_editing import (
    ProductionWorkspaceEditingComposition,
    ProductionWorkspaceEditingOptions,
)
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import AsyncRegisteredTool
from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    MutationDispositionStatus,
)
from fabrica.features.workspace_editing.application.dtos import WorkspaceMutationStartupGate
from fabrica.features.workspace_editing.application.errors import patch_error


def test_composition_exposes_only_default_tools_after_successful_gate(monkeypatch) -> None:
    events: list[str] = []
    _install_tool_factories(monkeypatch, events)
    monkeypatch.setattr(
        composition,
        "create_production_workspace_editing_composition",
        _enabled_editing_composition(events),
    )
    runtime_factory = _RuntimeFactory(events)
    monkeypatch.setattr(composition, "create_interactive_tool_loop_runtime", runtime_factory.create)
    options = _options(events)

    runtime = asyncio.run(composition.create_workspace_coding_agent_session_runtime(options=options))

    assert tuple(tool.name for tool in runtime.available_tools) == (
        "read_files",
        "search_codebase",
        "run_commands",
        "apply_patch",
        "ask_question",
    )
    assert events == ["read", "search", "commands", "gate", "model", "interactive"]
    assert runtime.mutation_gate.mutation_enabled is True


def test_composition_retains_read_only_tools_and_omits_apply_patch_after_failed_gate(monkeypatch) -> None:
    events: list[str] = []
    _install_tool_factories(monkeypatch, events)
    error = patch_error(
        "RECOVERY_REQUIRED",
        message="operator recovery required",
        metadata={"journal_digest": "sha256:" + "a" * 64},
    )

    async def compose_editing(*_args: object, read_only_tools: tuple[AsyncRegisteredTool, ...], **_kwargs: object):
        events.append("gate")
        return ProductionWorkspaceEditingComposition(
            tools=read_only_tools,
            mutation_gate=WorkspaceMutationStartupGate(mutation_enabled=False, error=error),
        )

    runtime_factory = _RuntimeFactory(events)
    monkeypatch.setattr(composition, "create_production_workspace_editing_composition", compose_editing)
    monkeypatch.setattr(composition, "create_interactive_tool_loop_runtime", runtime_factory.create)

    runtime = asyncio.run(composition.create_workspace_coding_agent_session_runtime(options=_options(events)))

    assert tuple(tool.name for tool in runtime.available_tools) == (
        "read_files",
        "search_codebase",
        "run_commands",
        "ask_question",
    )
    assert runtime.mutation_gate.mutation_enabled is False
    assert runtime.mutation_gate.reason == "RECOVERY_REQUIRED"
    assert events == ["read", "search", "commands", "gate", "model", "interactive"]


def test_runtime_derives_applied_mutation_only_from_committed_tool_evidence() -> None:
    runtime = composition.WorkspaceCodingAgentSessionRuntime(
        workspace_root=Path("/workspace"),
        runtime=_FakeInteractiveRuntime(
            ToolLoopRunResult(
                status=ToolLoopRunStatus.SUCCESS,
                tool_results=(_tool_result('{"mutation_guarantee":"committed"}'),),
            )
        ),
        mutation_gate=composition.MutationGateEvidence(mutation_enabled=True),
    )

    result = asyncio.run(runtime.run(CodingAgentSessionCommand(workspace_root=Path("/workspace"), prompt="Edit it")))

    assert result.mutation_disposition.status is MutationDispositionStatus.APPLIED


def test_runtime_rejects_command_for_a_different_workspace_before_model_execution() -> None:
    interactive_runtime = _FakeInteractiveRuntime(ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS))
    runtime = composition.WorkspaceCodingAgentSessionRuntime(
        workspace_root=Path("/workspace"),
        runtime=interactive_runtime,
        mutation_gate=composition.MutationGateEvidence(mutation_enabled=True),
    )

    with pytest.raises(ValueError, match="session command workspace_root must match the composed workspace root"):
        asyncio.run(runtime.run(CodingAgentSessionCommand(workspace_root=Path("/other"), prompt="Inspect")))
    assert interactive_runtime.calls == []


def _install_tool_factories(monkeypatch, events: list[str]) -> None:
    def read(*_args: object, **_kwargs: object) -> AsyncRegisteredTool:
        events.append("read")
        return _tool("read_files")

    def search(*_args: object, **_kwargs: object) -> AsyncRegisteredTool:
        events.append("search")
        return _tool("search_codebase")

    def commands(*_args: object, **_kwargs: object) -> AsyncRegisteredTool:
        events.append("commands")
        return _tool("run_commands")

    monkeypatch.setattr(composition, "create_read_files_registered_tool_adapter", read)
    monkeypatch.setattr(composition, "create_search_codebase_registered_tool_adapter", search)
    monkeypatch.setattr(composition, "create_run_commands_registered_tool_adapter", commands)


def _enabled_editing_composition(events: list[str]):
    async def compose_editing(*_args: object, read_only_tools: tuple[AsyncRegisteredTool, ...], **_kwargs: object):
        events.append("gate")
        return ProductionWorkspaceEditingComposition(
            tools=(*read_only_tools, _tool("apply_patch")),
            mutation_gate=WorkspaceMutationStartupGate(mutation_enabled=True),
        )

    return compose_editing


def _options(events: list[str]) -> composition.CodingAgentSessionOptions:
    def model_factory() -> object:
        events.append("model")
        return object()

    async def approve_patch(_plan: object) -> object:
        raise AssertionError

    return composition.CodingAgentSessionOptions(
        workspace_root=Path("/workspace"),
        model_factory=model_factory,  # ty: ignore[invalid-argument-type]
        interaction_transport=object(),  # ty: ignore[invalid-argument-type]
        command_options=RunCommandsToolOptions(
            shell_executable="/bin/sh",
            environment_builder=object(),  # ty: ignore[invalid-argument-type]
            permission_evaluator=object(),  # ty: ignore[invalid-argument-type]
            approval_resolver=object(),  # ty: ignore[invalid-argument-type]
            sandbox_preflight=object(),  # ty: ignore[invalid-argument-type]
        ),
        mutation_options=ProductionWorkspaceEditingOptions(approval_callback=approve_patch),  # ty: ignore[invalid-argument-type]
        read_files_external_authorized=True,
        read_files_image_input_supported=False,
    )


def _tool(name: str) -> AsyncRegisteredTool:
    async def handle(*_args: object) -> RegisteredToolOutcome:
        raise AssertionError

    return AsyncRegisteredTool(definition=ToolDefinition(name=name, description=f"{name} fixture."), handler=handle)


def _tool_result(result_text: str) -> ToolCallResult:
    return ToolCallResult(
        call_id="patch-1", tool_name="apply_patch", status=ToolCallResultStatus.SUCCESS, result_text=result_text
    )


@dataclass
class _RuntimeFactory:
    events: list[str]

    def create(self, *, tools: tuple[AsyncRegisteredTool, ...], **_kwargs: object) -> _FakeInteractiveRuntime:
        self.events.append("interactive")
        return _FakeInteractiveRuntime(
            ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS),
            (*tuple(tool.definition.name for tool in tools), "ask_question"),
        )


@dataclass
class _FakeInteractiveRuntime:
    result: ToolLoopRunResult
    tool_names: tuple[str, ...] = ()
    calls: list[object] = field(default_factory=list)

    @property
    def available_tools(self) -> tuple[ToolDefinition, ...]:
        return tuple(ToolDefinition(name=name, description=f"{name} fixture.") for name in self.tool_names)

    async def run(self, command: object, **_kwargs: object) -> ToolLoopRunResult:
        self.calls.append(command)
        return self.result
