"""Tests for workspace-scoped coding-agent session composition."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

import fabrica.bootstrap.composition.coding_agent_session as composition
from fabrica.bootstrap.composition.user_interaction import InteractiveToolLoopObservationOptions
from fabrica.bootstrap.composition.workspace_command_execution import RunCommandsToolOptions
from fabrica.bootstrap.composition.workspace_editing import (
    ProductionWorkspaceEditingComposition,
    ProductionWorkspaceEditingOptions,
)
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import AsyncRegisteredTool
from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    RuntimeObservation,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.agent_session.adapters.outbound.posix_filesystem import (
    PosixSessionRecordStore,
    PosixWorkspaceFingerprintBuilder,
)
from fabrica.features.agent_session.application import AcknowledgeStaleContextPlan, ReplanSafetyGate
from fabrica.features.agent_session.application.dtos import SessionCheckpoint, SessionEvent, WorkspaceFingerprint
from fabrica.features.agent_session.domain import SessionState
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


def test_replan_gated_executor_rejects_side_effects_until_inspection_and_current_plan_acknowledgement() -> None:
    delegate = _RecordingToolExecutor()
    store = _SessionStore()
    gate = ReplanSafetyGate(AcknowledgeStaleContextPlan(store, "session"))
    executor = composition.ReplanGatedToolExecutor(delegate, gate)
    limits = ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=100)
    cancellation = _NeverCancelledToolCancellationSignal()

    rejected_before_inspection = asyncio.run(
        executor.execute_tool(ToolCallRequest("command-before", "run_commands"), limits, cancellation)
    )
    inspection = asyncio.run(executor.execute_tool(ToolCallRequest("read", "read_files"), limits, cancellation))
    rejected_before_acknowledgement = asyncio.run(
        executor.execute_tool(ToolCallRequest("patch-before", "apply_patch"), limits, cancellation)
    )
    gate.display_refreshed_plan("sha256:" + "a" * 64)
    gate.acknowledge_displayed_plan(acknowledged=True)
    permitted = asyncio.run(executor.execute_tool(ToolCallRequest("patch-after", "apply_patch"), limits, cancellation))

    assert rejected_before_inspection.status is ToolCallResultStatus.REJECTED
    assert rejected_before_inspection.error_message == "fresh workspace inspection is required before side effects"
    assert inspection.status is ToolCallResultStatus.SUCCESS
    assert rejected_before_acknowledgement.status is ToolCallResultStatus.REJECTED
    assert (
        rejected_before_acknowledgement.error_message
        == "displayed refreshed-plan acknowledgement is required before side effects"
    )
    assert permitted.status is ToolCallResultStatus.SUCCESS
    assert tuple(request.tool_name for request in delegate.requests) == ("read_files", "apply_patch")


def test_composition_supplies_replan_executor_decoration_only_when_requested(monkeypatch) -> None:
    events: list[str] = []
    _install_tool_factories(monkeypatch, events)
    monkeypatch.setattr(
        composition,
        "create_production_workspace_editing_composition",
        _enabled_editing_composition(events),
    )
    runtime_factory = _RuntimeFactory(events)
    monkeypatch.setattr(composition, "create_interactive_tool_loop_runtime", runtime_factory.create)
    replan_gate = ReplanSafetyGate(AcknowledgeStaleContextPlan(_SessionStore(), "session"))

    asyncio.run(
        composition.create_workspace_coding_agent_session_runtime(
            options=replace(_options(events), replan_safety_gate=replan_gate)
        )
    )

    observation_options = runtime_factory.calls[0]["observation_options"]
    assert isinstance(observation_options, InteractiveToolLoopObservationOptions)
    assert observation_options.tool_executor_decorator is not None
    decorated = observation_options.tool_executor_decorator(_RecordingToolExecutor())
    assert isinstance(decorated, composition.ReplanGatedToolExecutor)


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


def test_resume_composition_reuses_session_id_and_injects_bounded_context_into_a_fresh_turn(
    monkeypatch, tmp_path
) -> None:
    events: list[str] = []
    _install_tool_factories(monkeypatch, events)
    monkeypatch.setattr(
        composition,
        "create_production_workspace_editing_composition",
        _enabled_editing_composition(events),
    )
    runtime_factory = _RuntimeFactory(events)
    monkeypatch.setattr(composition, "create_interactive_tool_loop_runtime", runtime_factory.create)
    session_id = "session_resume"
    _save_resumable_checkpoint(tmp_path, session_id)
    options = replace(_options(events), workspace_root=tmp_path)

    prepared = asyncio.run(
        composition.prepare_workspace_coding_agent_session_resume_runtime(options=options, session_id=session_id)
    )
    assert prepared.preparation.disposition is composition.ResumeDisposition.RESUME
    assert prepared.runtime is not None

    asyncio.run(prepared.runtime.run(CodingAgentSessionCommand(workspace_root=tmp_path, prompt="Continue safely.")))

    interactive_runtime = runtime_factory.runtimes[0]
    runtime_command = interactive_runtime.calls[0]
    assert isinstance(runtime_command, composition.LocalAgentRunCommand)
    assert runtime_command.prompt == "Continue safely."
    assert runtime_command.context[0].label == "Safe durable session resume context"
    assert "Completed checkpoint: finished safely" in runtime_command.context[0].text
    checkpoint_sequence = 2
    assert runtime_command.context[0].metadata == {"session_id": session_id, "checkpoint_sequence": checkpoint_sequence}
    stored_events = PosixSessionRecordStore(tmp_path).load_events(session_id)
    assert stored_events[-2].sequence > checkpoint_sequence


def test_stale_resume_composition_enables_replan_executor_gate_without_reusing_context(monkeypatch, tmp_path) -> None:
    events: list[str] = []
    _install_tool_factories(monkeypatch, events)
    monkeypatch.setattr(
        composition,
        "create_production_workspace_editing_composition",
        _enabled_editing_composition(events),
    )
    runtime_factory = _RuntimeFactory(events)
    monkeypatch.setattr(composition, "create_interactive_tool_loop_runtime", runtime_factory.create)
    _save_resumable_checkpoint(tmp_path, "session_stale", digest="sha256:" + "b" * 64)

    prepared = asyncio.run(
        composition.prepare_workspace_coding_agent_session_resume_runtime(
            options=replace(_options(events), workspace_root=tmp_path),
            session_id="session_stale",
        )
    )

    assert prepared.preparation.disposition is composition.ResumeDisposition.STALE_CONTEXT
    assert prepared.runtime is not None
    assert prepared.runtime.resume_context is None
    observation_options = runtime_factory.calls[0]["observation_options"]
    assert isinstance(observation_options, InteractiveToolLoopObservationOptions)
    assert observation_options.tool_executor_decorator is not None
    assert isinstance(
        observation_options.tool_executor_decorator(_RecordingToolExecutor()), composition.ReplanGatedToolExecutor
    )


def test_unavailable_resume_composition_fails_closed_without_constructing_a_runtime(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        composition, "create_interactive_tool_loop_runtime", lambda **_kwargs: pytest.fail("unexpected")
    )

    prepared = asyncio.run(
        composition.prepare_workspace_coding_agent_session_resume_runtime(
            options=replace(_options([]), workspace_root=tmp_path),
            session_id="missing",
        )
    )

    assert prepared.preparation.disposition is composition.ResumeDisposition.UNAVAILABLE
    assert prepared.runtime is None


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
    calls: list[dict[str, object]] = field(default_factory=list)
    runtimes: list[_FakeInteractiveRuntime] = field(default_factory=list)

    def create(self, *, tools: tuple[AsyncRegisteredTool, ...], **_kwargs: object) -> _FakeInteractiveRuntime:
        self.events.append("interactive")
        self.calls.append(_kwargs)
        runtime = _FakeInteractiveRuntime(
            ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS),
            (*tuple(tool.definition.name for tool in tools), "ask_question"),
        )
        self.runtimes.append(runtime)
        return runtime


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


@dataclass
class _RecordingToolExecutor:
    requests: list[ToolCallRequest] = field(default_factory=list)

    async def execute_tool(
        self,
        request: ToolCallRequest,
        limits: ToolLoopLimits,
        cancellation: composition.ToolCancellationSignal,
        opaque_context: Mapping[str, object] | None = None,
    ) -> ToolCallResult:
        del limits, cancellation, opaque_context
        self.requests.append(request)
        return ToolCallResult(
            call_id=request.call_id,
            tool_name=request.tool_name,
            status=ToolCallResultStatus.SUCCESS,
            observations=(RuntimeObservation(message="synthetic tool completed"),),
        )


class _NeverCancelledToolCancellationSignal:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        await asyncio.Event().wait()


@dataclass
class _SessionStore:
    events: list[SessionEvent] = field(default_factory=list)
    checkpoints: list[SessionCheckpoint] = field(default_factory=list)

    def append_event(self, event: SessionEvent) -> None:
        self.events.append(event)

    def save_checkpoint(self, checkpoint: SessionCheckpoint) -> None:
        self.checkpoints.append(checkpoint)

    def load_events(self, session_id: str) -> tuple[SessionEvent, ...]:
        return tuple(event for event in self.events if event.session_id == session_id)

    def load_checkpoint(self, session_id: str) -> SessionCheckpoint | None:
        return next(
            (checkpoint for checkpoint in reversed(self.checkpoints) if checkpoint.session_id == session_id), None
        )

    def list_session_ids(self) -> tuple[str, ...]:
        return ()

    def delete_session(self, session_id: str) -> None:
        del session_id

    def export_session(self, session_id: str, destination: Path) -> Path:
        del session_id
        return destination


def _save_resumable_checkpoint(
    workspace_root: Path,
    session_id: str,
    *,
    digest: str | None = None,
) -> None:
    store = PosixSessionRecordStore(workspace_root)
    store.append_event(SessionEvent(session_id, 0, "started"))
    store.append_event(SessionEvent(session_id, 1, "completed"))
    store.append_event(SessionEvent(session_id, 2, "completed"))
    store.save_checkpoint(
        SessionCheckpoint(
            session_id=session_id,
            sequence=2,
            state=SessionState.COMPLETED,
            workspace_fingerprint=(
                WorkspaceFingerprint(digest=digest)
                if digest is not None
                else PosixWorkspaceFingerprintBuilder(workspace_root).build()
            ),
            completed_summary="finished safely",
        )
    )
