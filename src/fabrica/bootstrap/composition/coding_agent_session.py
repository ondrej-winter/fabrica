"""Bootstrap composition for the restricted workspace coding-agent session."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fabrica.bootstrap.composition.skill_context import (
    SkillContextAugmentationOptions,
    create_skill_context_augmented_local_agent_command,
)
from fabrica.bootstrap.composition.user_interaction import create_interactive_tool_loop_runtime
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
    LocalAgentRunCommand,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopRunResult,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModel
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionRuntimeResult,
    MutationDisposition,
    MutationDispositionStatus,
    MutationGateEvidence,
)
from fabrica.features.user_interaction.application.ports import InteractionTransport
from fabrica.features.workspace_editing.application.dtos import WorkspaceMutationStartupGate
from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits
from fabrica.features.workspace_searching.application.dtos import SearchLimits

_APPLY_PATCH_TOOL_NAME = "apply_patch"
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

    def __post_init__(self) -> None:
        workspace_root = Path(self.workspace_root)
        if not workspace_root.is_absolute():
            msg = "workspace_root must be canonical and absolute"
            raise ValueError(msg)
        object.__setattr__(self, "workspace_root", workspace_root)


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
class WorkspaceCodingAgentSessionRuntime:
    """Run sessions through tools composed for one canonical workspace root."""

    workspace_root: Path
    runtime: _InteractiveSessionRuntime
    mutation_gate: MutationGateEvidence
    selected_context_options: SkillContextAugmentationOptions | None = None

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
        runtime_command = LocalAgentRunCommand(prompt=command.prompt)
        runtime_command = _augment_selected_context(runtime_command, command, self.selected_context_options)
        tool_loop_result = await self.runtime.run(runtime_command, cancellation=cancellation)
        return CodingAgentSessionRuntimeResult(
            tool_loop_result=tool_loop_result,
            mutation_gate=self.mutation_gate,
            mutation_disposition=_mutation_disposition(tool_loop_result),
        )


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
    runtime = create_interactive_tool_loop_runtime(
        model=model,
        transport=options.interaction_transport,
        tools=editing_composition.tools,
    )
    return WorkspaceCodingAgentSessionRuntime(
        workspace_root=options.workspace_root,
        runtime=runtime,
        mutation_gate=_mutation_gate_evidence(editing_composition.mutation_gate),
        selected_context_options=options.selected_context_options,
    )


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
    "create_workspace_coding_agent_session_runtime",
]
