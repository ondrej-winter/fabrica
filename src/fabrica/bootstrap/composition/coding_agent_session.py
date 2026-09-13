"""Bootstrap composition for the restricted workspace coding-agent session."""

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO
from uuid import uuid4

from fabrica.bootstrap.composition.codex_runtime import create_codex_tool_aware_model
from fabrica.bootstrap.composition.skill_context import (
    SkillContextAugmentationOptions,
    create_skill_context_augmented_local_agent_command,
)
from fabrica.bootstrap.composition.user_interaction import (
    InteractiveToolLoopObservationOptions,
    active_interactive_run,
    create_interactive_tool_loop_runtime,
)
from fabrica.bootstrap.composition.workspace_command_execution import (
    RunCommandsToolOptions,
    create_run_commands_registered_tool_adapter,
)
from fabrica.bootstrap.composition.workspace_editing import (
    ProductionWorkspaceEditingOptions,
    create_production_workspace_editing_composition,
)
from fabrica.bootstrap.composition.workspace_reading import create_read_files_registered_tool_adapter
from fabrica.bootstrap.composition.workspace_searching import create_search_codebase_registered_tool_adapter
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    RuntimeObservation,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModel, ToolExecutor
from fabrica.features.agent_session.adapters.outbound.posix_filesystem import (
    PosixSessionRecordStore,
    PosixWorkspaceFingerprintBuilder,
)
from fabrica.features.agent_session.application import (
    AcknowledgeStaleContextPlan,
    PrepareSessionResume,
    RecordSessionLifecycle,
    ReplanSafetyGate,
    ResumeDisposition,
    SessionRecordingError,
    SessionResumePreparation,
)
from fabrica.features.agent_session.application.dtos import ResumeContext
from fabrica.features.coding_agent_session.adapters.inbound.terminal import (
    TerminalCommandApprovalResolver,
    TerminalPatchApproval,
    TerminalQuestionTransport,
)
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionRuntimeResult,
    MutationDisposition,
    MutationDispositionStatus,
    MutationGateEvidence,
)
from fabrica.features.user_interaction.application.ports import InteractionTransport
from fabrica.features.workspace_command_execution.adapters.outbound.authorization import (
    HostCommandPermissionEvaluator,
    HostCommandSandboxPreflight,
)
from fabrica.features.workspace_command_execution.adapters.outbound.environment import FilteredCommandEnvironmentBuilder
from fabrica.features.workspace_command_execution.application.dtos import CommandExecutionMode, PlannedCommand
from fabrica.features.workspace_command_execution.application.ports import CommandPermissionDecision
from fabrica.features.workspace_editing.application.dtos import WorkspaceMutationStartupGate
from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits
from fabrica.features.workspace_searching.application.dtos import SearchLimits

_APPLY_PATCH_TOOL_NAME = "apply_patch"
_RUN_COMMANDS_TOOL_NAME = "run_commands"
_FRESH_INSPECTION_TOOL_NAMES = frozenset({"read_files", "search_codebase"})
_COMMITTED_MUTATION_GUARANTEE = "committed"
_NO_MUTATION_GUARANTEE = "no_mutation"


@dataclass(frozen=True, slots=True)
class CodingAgentSessionOptions:
    """Explicit host dependencies and limits for one workspace-scoped session."""

    workspace_root: Path
    model_factory: Callable[[], ToolAwareAgentModel]
    interaction_transport: InteractionTransport
    command_options: RunCommandsToolOptions
    mutation_options: ProductionWorkspaceEditingOptions
    read_files_external_authorized: bool
    read_files_image_input_supported: bool
    read_files_limits: ReadFilesLimits | None = None
    search_limits: SearchLimits | None = None
    selected_context_options: SkillContextAugmentationOptions | None = None
    replan_safety_gate: ReplanSafetyGate | None = None
    session_id: str | None = None
    resume_context: ResumeContext | None = None

    def __post_init__(self) -> None:
        workspace_root = Path(self.workspace_root)
        if not workspace_root.is_absolute():
            msg = "workspace_root must be canonical and absolute"
            raise ValueError(msg)
        object.__setattr__(self, "workspace_root", workspace_root)
        if self.resume_context is not None and self.session_id != self.resume_context.checkpoint.session_id:
            msg = "resume context must use its checkpoint session ID"
            raise ValueError(msg)


class _InteractiveSessionRuntime(Protocol):
    """Required interactive runtime surface for one composed session."""

    @property
    def available_tools(self) -> tuple[ToolDefinition, ...]:
        """Return the definitions made available to the model."""

    async def run(
        self,
        command: LocalAgentRunCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolLoopRunResult:
        """Run one interactive tool-loop session."""


@dataclass(frozen=True, slots=True)
class ReplanGatedToolExecutor:
    """Block stale-context side effects until host-owned replan prerequisites hold."""

    delegate: ToolExecutor
    gate: ReplanSafetyGate

    async def execute_tool(
        self,
        request: ToolCallRequest,
        limits: ToolLoopLimits,
        cancellation: ToolCancellationSignal,
        opaque_context: Mapping[str, object] | None = None,
    ) -> ToolCallResult:
        """Delegate inspection but reject commands and patches before replan acknowledgement."""
        if (
            request.tool_name in {_RUN_COMMANDS_TOOL_NAME, _APPLY_PATCH_TOOL_NAME}
            and not self.gate.side_effects_permitted
        ):
            return ToolCallResult(
                call_id=request.call_id,
                tool_name=request.tool_name,
                status=ToolCallResultStatus.REJECTED,
                arguments=request.arguments,
                error_message=self.gate.side_effect_block_reason(),
                observations=(
                    RuntimeObservation(
                        message="stale-context replan blocked a side-effecting tool",
                        metadata={"tool_name": request.tool_name, "category": "stale_context_replan"},
                    ),
                ),
            )
        result = await self.delegate.execute_tool(request, limits, cancellation, opaque_context)
        if request.tool_name in _FRESH_INSPECTION_TOOL_NAMES and result.status is ToolCallResultStatus.SUCCESS:
            self.gate.record_fresh_inspection()
        return result


@dataclass(frozen=True, slots=True)
class WorkspaceCodingAgentSessionRuntime:
    """Run sessions through tools composed for one canonical workspace root."""

    workspace_root: Path
    runtime: _InteractiveSessionRuntime
    mutation_gate: MutationGateEvidence
    selected_context_options: SkillContextAugmentationOptions | None = None
    lifecycle_recorder: RecordSessionLifecycle | None = None
    resume_context: ResumeContext | None = None

    @property
    def available_tools(self) -> tuple[ToolDefinition, ...]:
        """Return the restricted tool definitions exposed by the composed runtime."""
        return self.runtime.available_tools

    async def run(
        self,
        command: CodingAgentSessionCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> CodingAgentSessionRuntimeResult:
        """Run explicit selected context through the pre-gated interactive tool loop."""
        if command.workspace_root != self.workspace_root:
            msg = "session command workspace_root must match the composed workspace root"
            raise ValueError(msg)
        runtime_command = _resume_aware_runtime_command(command.prompt, self.resume_context)
        runtime_command = _augment_selected_context(runtime_command, command, self.selected_context_options)
        if self.lifecycle_recorder is not None:
            try:
                self.lifecycle_recorder.start()
            except SessionRecordingError:
                return _recording_failure_result(self.mutation_gate)
        tool_loop_result = await self.runtime.run(runtime_command, cancellation=cancellation)
        if self.lifecycle_recorder is not None:
            try:
                self.lifecycle_recorder.finish(tool_loop_result)
            except SessionRecordingError:
                tool_loop_result = ToolLoopRunResult(
                    status=ToolLoopRunStatus.MODEL_ERROR,
                    tool_results=tool_loop_result.tool_results,
                    observations=(
                        *tool_loop_result.observations,
                        RuntimeObservation(message="durable session recording failed"),
                    ),
                )
        return CodingAgentSessionRuntimeResult(
            tool_loop_result=tool_loop_result,
            mutation_gate=self.mutation_gate,
            mutation_disposition=_mutation_disposition(tool_loop_result),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceSessionResumeRuntimePreparation:
    """Safe resume classification and runtime for one existing workspace session."""

    preparation: SessionResumePreparation
    runtime: WorkspaceCodingAgentSessionRuntime | None = None

    def __post_init__(self) -> None:
        if self.preparation.disposition is ResumeDisposition.UNAVAILABLE and self.runtime is not None:
            msg = "unavailable session evidence cannot produce a runtime"
            raise ValueError(msg)
        if self.preparation.disposition is not ResumeDisposition.UNAVAILABLE and self.runtime is None:
            msg = "available or stale session evidence requires a runtime"
            raise ValueError(msg)


async def create_workspace_coding_agent_session_runtime(
    *, options: CodingAgentSessionOptions
) -> WorkspaceCodingAgentSessionRuntime:
    """Compose the Version 1 restricted tool set after mutation startup gating.

    Model construction occurs only after workspace mutation recovery and capability
    verification. A failed mutation gate retains the four non-mutating tools and
    omits ``apply_patch``.
    """
    read_files = create_read_files_registered_tool_adapter(
        options.workspace_root,
        external_read_authorized=options.read_files_external_authorized,
        image_input_supported=options.read_files_image_input_supported,
        limits=options.read_files_limits,
    )
    search_codebase = create_search_codebase_registered_tool_adapter(
        options.workspace_root,
        limits=options.search_limits,
    )
    run_commands = create_run_commands_registered_tool_adapter(
        options.workspace_root,
        options=options.command_options,
    )
    editing_composition = await create_production_workspace_editing_composition(
        options.workspace_root,
        options=options.mutation_options,
        read_only_tools=(read_files, search_codebase, run_commands),
    )
    model = options.model_factory()
    session_id = options.session_id or f"session_{uuid4().hex}"
    lifecycle_recorder = RecordSessionLifecycle(
        session_id=session_id,
        store=PosixSessionRecordStore(options.workspace_root),
        fingerprint_builder=PosixWorkspaceFingerprintBuilder(options.workspace_root),
    )
    runtime = create_interactive_tool_loop_runtime(
        model=model,
        transport=options.interaction_transport,
        tools=editing_composition.tools,
        observation_options=InteractiveToolLoopObservationOptions(
            model_response_observer=lifecycle_recorder.record_model_response,
            tool_result_observer=lifecycle_recorder.record_tool_result,
            tool_executor_decorator=_replan_executor_decorator(options.replan_safety_gate),
        ),
    )
    return WorkspaceCodingAgentSessionRuntime(
        workspace_root=options.workspace_root,
        runtime=runtime,
        mutation_gate=_mutation_gate_evidence(editing_composition.mutation_gate),
        selected_context_options=options.selected_context_options,
        lifecycle_recorder=lifecycle_recorder,
        resume_context=options.resume_context,
    )


async def prepare_workspace_coding_agent_session_resume_runtime(
    *,
    options: CodingAgentSessionOptions,
    session_id: str,
) -> WorkspaceSessionResumeRuntimePreparation:
    """Prepare an existing session for a fresh normal or stale-context runtime turn."""
    store = PosixSessionRecordStore(options.workspace_root)
    preparation = PrepareSessionResume(
        store=store,
        fingerprint_builder=PosixWorkspaceFingerprintBuilder(options.workspace_root),
    ).execute(session_id)
    if preparation.disposition is ResumeDisposition.UNAVAILABLE:
        return WorkspaceSessionResumeRuntimePreparation(preparation=preparation)
    resumed_options = CodingAgentSessionOptions(
        workspace_root=options.workspace_root,
        model_factory=options.model_factory,
        interaction_transport=options.interaction_transport,
        command_options=options.command_options,
        mutation_options=options.mutation_options,
        read_files_external_authorized=options.read_files_external_authorized,
        read_files_image_input_supported=options.read_files_image_input_supported,
        read_files_limits=options.read_files_limits,
        search_limits=options.search_limits,
        selected_context_options=options.selected_context_options,
        session_id=session_id,
        resume_context=preparation.resume_context,
        replan_safety_gate=(
            ReplanSafetyGate(AcknowledgeStaleContextPlan(store=store, session_id=session_id))
            if preparation.disposition is ResumeDisposition.STALE_CONTEXT
            else None
        ),
    )
    return WorkspaceSessionResumeRuntimePreparation(
        preparation=preparation,
        runtime=await create_workspace_coding_agent_session_runtime(options=resumed_options),
    )


async def create_terminal_workspace_coding_agent_session_runtime(
    *,
    workspace_root: Path,
    stdin: TextIO,
    stdout: TextIO,
    skill_roots: tuple[Path, ...] = (),
) -> WorkspaceCodingAgentSessionRuntime:
    """Compose the production terminal session with explicit command admission policy."""
    command_approval = TerminalCommandApprovalResolver(stdin=stdin, stdout=stdout)
    patch_approval = TerminalPatchApproval(stdin=stdin, stdout=stdout)
    interaction_transport = TerminalQuestionTransport(
        stdin=stdin,
        stdout=stdout,
        submit_answer=lambda submission: active_interactive_run().submit_answer(submission),
        cancel_question=lambda question_id: active_interactive_run().cancel_question(question_id.value),
    )
    command_options = RunCommandsToolOptions(
        shell_executable="/bin/sh",
        environment_builder=FilteredCommandEnvironmentBuilder(
            inherited_environment={"PATH": os.environ.get("PATH", "")},
            allowed_override_keys=frozenset(),
        ),
        permission_evaluator=HostCommandPermissionEvaluator(_terminal_command_permission),
        approval_resolver=command_approval,
        sandbox_preflight=HostCommandSandboxPreflight(_allow_terminal_sandbox),
    )
    return await create_workspace_coding_agent_session_runtime(
        options=_terminal_session_options(
            workspace_root=workspace_root,
            interaction_transport=interaction_transport,
            command_options=command_options,
            patch_approval=patch_approval,
            skill_roots=skill_roots,
        )
    )


async def prepare_terminal_workspace_coding_agent_session_resume_runtime(
    *,
    workspace_root: Path,
    session_id: str,
    stdin: TextIO,
    stdout: TextIO,
    skill_roots: tuple[Path, ...] = (),
) -> WorkspaceSessionResumeRuntimePreparation:
    """Prepare an existing terminal session without executing stale or unavailable evidence."""
    command_approval = TerminalCommandApprovalResolver(stdin=stdin, stdout=stdout)
    patch_approval = TerminalPatchApproval(stdin=stdin, stdout=stdout)
    interaction_transport = TerminalQuestionTransport(
        stdin=stdin,
        stdout=stdout,
        submit_answer=lambda submission: active_interactive_run().submit_answer(submission),
        cancel_question=lambda question_id: active_interactive_run().cancel_question(question_id.value),
    )
    command_options = RunCommandsToolOptions(
        shell_executable="/bin/sh",
        environment_builder=FilteredCommandEnvironmentBuilder(
            inherited_environment={"PATH": os.environ.get("PATH", "")},
            allowed_override_keys=frozenset(),
        ),
        permission_evaluator=HostCommandPermissionEvaluator(_terminal_command_permission),
        approval_resolver=command_approval,
        sandbox_preflight=HostCommandSandboxPreflight(_allow_terminal_sandbox),
    )
    return await prepare_workspace_coding_agent_session_resume_runtime(
        options=_terminal_session_options(
            workspace_root=workspace_root,
            interaction_transport=interaction_transport,
            command_options=command_options,
            patch_approval=patch_approval,
            skill_roots=skill_roots,
        ),
        session_id=session_id,
    )


def _terminal_session_options(
    *,
    workspace_root: Path,
    interaction_transport: InteractionTransport,
    command_options: RunCommandsToolOptions,
    patch_approval: TerminalPatchApproval,
    skill_roots: tuple[Path, ...],
) -> CodingAgentSessionOptions:
    return CodingAgentSessionOptions(
        workspace_root=workspace_root,
        model_factory=create_codex_tool_aware_model,
        interaction_transport=interaction_transport,
        command_options=command_options,
        mutation_options=ProductionWorkspaceEditingOptions(approval_callback=patch_approval.decide),
        read_files_external_authorized=False,
        read_files_image_input_supported=False,
        selected_context_options=SkillContextAugmentationOptions(skill_roots=skill_roots),
    )


async def _terminal_command_permission(command: PlannedCommand) -> CommandPermissionDecision:
    if command.request.mode is not CommandExecutionMode.ARGV:
        return CommandPermissionDecision.DENY
    argv = command.request.argv or ()
    if not argv or argv[0] == "git" or _has_interactive_or_background_form(argv):
        return CommandPermissionDecision.DENY
    return CommandPermissionDecision.REQUIRE_APPROVAL


async def _allow_terminal_sandbox(command: PlannedCommand) -> bool:
    del command
    return True


def _has_interactive_or_background_form(argv: tuple[str, ...]) -> bool:
    return any(argument in {"&", "-i", "--interactive"} for argument in argv)


def _replan_executor_decorator(gate: ReplanSafetyGate | None) -> Callable[[ToolExecutor], ToolExecutor] | None:
    if gate is None:
        return None
    return lambda executor: ReplanGatedToolExecutor(executor, gate)


def _augment_selected_context(
    command: LocalAgentRunCommand,
    session_command: CodingAgentSessionCommand,
    options: SkillContextAugmentationOptions | None,
) -> LocalAgentRunCommand:
    if not session_command.selected_skills and not session_command.selected_resources:
        return command
    base_options = options or SkillContextAugmentationOptions()
    return create_skill_context_augmented_local_agent_command(
        command,
        SkillContextAugmentationOptions(
            skill_selections=session_command.selected_skills,
            resource_selections=session_command.selected_resources,
            skill_roots=base_options.skill_roots,
            skill_bounds=base_options.skill_bounds,
            resource_bounds=base_options.resource_bounds,
            verbose_diagnostics=base_options.verbose_diagnostics,
        ),
    )


def _resume_aware_runtime_command(prompt: str, resume_context: ResumeContext | None) -> LocalAgentRunCommand:
    """Create a fresh turn command with bounded completed evidence when normal resume is safe."""
    if resume_context is None:
        return LocalAgentRunCommand(prompt=prompt)
    checkpoint = resume_context.checkpoint
    evidence_lines = [
        resume_context.continuation_instruction,
        f"Completed checkpoint: {checkpoint.completed_summary}",
        f"Checkpoint state: {checkpoint.state.value}",
        f"Completed events after checkpoint: {len(resume_context.later_events)}",
    ]
    return LocalAgentRunCommand(
        prompt=prompt,
        context=(
            LocalAgentContextBlock(
                text="\n".join(evidence_lines),
                label="Safe durable session resume context",
                metadata={"session_id": checkpoint.session_id, "checkpoint_sequence": checkpoint.sequence},
            ),
        ),
    )


def _mutation_gate_evidence(gate: WorkspaceMutationStartupGate) -> MutationGateEvidence:
    if gate.mutation_enabled:
        return MutationGateEvidence(
            mutation_enabled=True,
            recovered_journal_digests=gate.recovered_journal_digests,
        )
    error = gate.error
    reason = error.code if error is not None else "mutation startup gate failed"
    return MutationGateEvidence(
        mutation_enabled=False,
        reason=reason,
        recovered_journal_digests=gate.recovered_journal_digests,
    )


def _recording_failure_result(mutation_gate: MutationGateEvidence) -> CodingAgentSessionRuntimeResult:
    return CodingAgentSessionRuntimeResult(
        tool_loop_result=ToolLoopRunResult(
            status=ToolLoopRunStatus.MODEL_ERROR,
            observations=(RuntimeObservation(message="durable session recording failed"),),
        ),
        mutation_gate=mutation_gate,
        mutation_disposition=MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED),
    )


def _mutation_disposition(result: ToolLoopRunResult) -> MutationDisposition:
    apply_patch_results = tuple(item for item in result.tool_results if item.tool_name == _APPLY_PATCH_TOOL_NAME)
    if not apply_patch_results:
        return MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED)

    guarantees = tuple(_mutation_guarantee(item.result_text) for item in apply_patch_results)
    if any(guarantee is None for guarantee in guarantees):
        return MutationDisposition(MutationDispositionStatus.INDETERMINATE, (_APPLY_PATCH_TOOL_NAME,))
    if any(guarantee not in {_COMMITTED_MUTATION_GUARANTEE, _NO_MUTATION_GUARANTEE} for guarantee in guarantees):
        return MutationDisposition(MutationDispositionStatus.INDETERMINATE, (_APPLY_PATCH_TOOL_NAME,))
    if any(guarantee == _COMMITTED_MUTATION_GUARANTEE for guarantee in guarantees):
        return MutationDisposition(MutationDispositionStatus.APPLIED, (_APPLY_PATCH_TOOL_NAME,))
    return MutationDisposition(MutationDispositionStatus.NOT_APPLIED, (_APPLY_PATCH_TOOL_NAME,))


def _mutation_guarantee(result_text: str | None) -> str | None:
    if result_text is None:
        return None
    try:
        payload = json.loads(result_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    guarantee = payload.get("mutation_guarantee")
    return guarantee if isinstance(guarantee, str) else None


__all__ = [
    "CodingAgentSessionOptions",
    "WorkspaceCodingAgentSessionRuntime",
    "create_terminal_workspace_coding_agent_session_runtime",
    "create_workspace_coding_agent_session_runtime",
]
