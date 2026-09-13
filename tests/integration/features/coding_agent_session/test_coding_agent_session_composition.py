"""Offline integration coverage for the workspace-scoped coding-agent session."""

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from fabrica.bootstrap.composition.coding_agent_session import (
    CodingAgentSessionOptions,
    create_workspace_coding_agent_session_runtime,
)
from fabrica.bootstrap.composition.workspace_command_execution import RunCommandsToolOptions
from fabrica.bootstrap.composition.workspace_editing import ProductionWorkspaceEditingOptions
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopRunStatus,
)
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    MutationDispositionStatus,
)
from fabrica.features.user_interaction.application.dtos import InteractionPublication
from fabrica.features.workspace_command_execution.adapters.outbound.authorization import (
    HostCommandApprovalResolver,
    HostCommandPermissionEvaluator,
    HostCommandSandboxPreflight,
)
from fabrica.features.workspace_command_execution.adapters.outbound.environment import FilteredCommandEnvironmentBuilder
from fabrica.features.workspace_command_execution.application.dtos import PlannedCommand
from fabrica.features.workspace_command_execution.application.ports import CommandPermissionDecision
from fabrica.features.workspace_editing.application.dtos import PatchApprovalDecision, PatchPlan

EXPECTED_MODEL_TURN_COUNT = 4
VALIDATION_COMMAND = "from pathlib import Path; assert Path('validated.txt').read_text() == 'validated\\n'"


@dataclass(slots=True)
class _ScriptedSessionModel:
    """Request the inspect, patch, and validation workflow in fixed order."""

    responses: list[ToolAwareModelResponse]
    calls: list[tuple[LocalAgentRunCommand, tuple[ToolDefinition, ...], tuple[ToolCallResult, ...]]] = field(
        default_factory=list,
    )

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        """Return the next predeclared model turn without external effects."""
        del cancellation
        self.calls.append((command, available_tools, tool_results))
        return self.responses.pop(0)


@dataclass(slots=True)
class _UnusedInteractionTransport:
    """Fail if the scripted non-interactive workflow unexpectedly asks a question."""

    async def publish(self, publication: InteractionPublication) -> None:
        """Reject an unexpected interactive request."""
        msg = f"unexpected question: {publication.question.question}"
        raise AssertionError(msg)


@dataclass(slots=True)
class _ApprovalRecorder:
    """Approve exact patch plans and validation commands while recording both."""

    patch_digests: list[str] = field(default_factory=list)
    commands: list[PlannedCommand] = field(default_factory=list)

    async def approve_patch(self, plan: PatchPlan) -> PatchApprovalDecision:
        """Approve the immutable plan digest rendered by the patch primitive."""
        self.patch_digests.append(plan.plan_digest)
        return PatchApprovalDecision(approved=True, plan_digest=plan.plan_digest)

    async def approve_command(self, command: PlannedCommand) -> bool:
        """Approve the resolved command after static policy has admitted it."""
        self.commands.append(command)
        return True


def test_session_composition_inspects_applies_digest_bound_patch_and_validates_workspace(tmp_path: Path) -> None:
    """Run the normal offline inspect-edit-validate session workflow end to end."""
    source_file = tmp_path / "note.txt"
    source_file.write_text("original\n", encoding="utf-8")
    approval = _ApprovalRecorder()
    model = _ScriptedSessionModel(
        responses=[
            ToolAwareModelResponse(
                tool_calls=(
                    ToolCallRequest(
                        call_id="read-note",
                        tool_name="read_files",
                        arguments={"files": ({"path": "note.txt"},)},
                    ),
                ),
            ),
            ToolAwareModelResponse(
                tool_calls=(
                    ToolCallRequest(
                        call_id="patch-note",
                        tool_name="apply_patch",
                        arguments={"input": "*** Begin Patch\n*** Add File: validated.txt\n+validated\n*** End Patch"},
                    ),
                ),
            ),
            ToolAwareModelResponse(
                tool_calls=(
                    ToolCallRequest(
                        call_id="validate-note",
                        tool_name="run_commands",
                        arguments={
                            "commands": (
                                {
                                    "argv": (
                                        sys.executable,
                                        "-c",
                                        VALIDATION_COMMAND,
                                    ),
                                    "timeout_ms": 5_000,
                                },
                            ),
                        },
                    ),
                ),
            ),
            ToolAwareModelResponse(output_text="Updated note.txt and validated it."),
        ],
    )

    runtime = asyncio.run(
        create_workspace_coding_agent_session_runtime(
            options=_options(workspace_root=tmp_path, model=model, approval=approval),
        )
    )
    result = asyncio.run(runtime.run(CodingAgentSessionCommand(workspace_root=tmp_path, prompt="Update the note.")))

    assert tuple(tool.name for tool in runtime.available_tools) == (
        "read_files",
        "search_codebase",
        "run_commands",
        "apply_patch",
        "ask_question",
    )
    assert result.tool_loop_result.status is ToolLoopRunStatus.SUCCESS
    assert result.tool_loop_result.output_text == "Updated note.txt and validated it."
    assert tuple(tool_result.tool_name for tool_result in result.tool_loop_result.tool_results) == (
        "read_files",
        "apply_patch",
        "run_commands",
    )
    assert result.mutation_disposition.status is MutationDispositionStatus.APPLIED
    assert len(approval.patch_digests) == 1
    assert len(approval.commands) == 1
    assert approval.commands[0].request.argv == (
        sys.executable,
        "-c",
        VALIDATION_COMMAND,
    )
    assert source_file.read_text(encoding="utf-8") == "original\n"
    assert (tmp_path / "validated.txt").read_text(encoding="utf-8") == "validated\n"
    assert len(model.calls) == EXPECTED_MODEL_TURN_COUNT
    event_paths = tuple((tmp_path / ".fabrica" / "sessions").glob("*/events.jsonl"))
    assert len(event_paths) == 1
    journal = event_paths[0].read_text(encoding="utf-8")
    events = tuple(json.loads(line) for line in journal.splitlines())
    assert [event["kind"] for event in events] == [
        "sensitivity_warning",
        "state_changed",
        "model_turn_completed",
        "tool_call_completed",
        "model_turn_completed",
        "tool_call_completed",
        "model_turn_completed",
        "tool_call_completed",
        "model_turn_completed",
        "run_completed",
        "state_changed",
    ]
    assert "Update the note." not in journal
    assert VALIDATION_COMMAND not in journal


def _options(
    *,
    workspace_root: Path,
    model: _ScriptedSessionModel,
    approval: _ApprovalRecorder,
) -> CodingAgentSessionOptions:
    async def require_approval(command: PlannedCommand) -> CommandPermissionDecision:
        del command
        return CommandPermissionDecision.REQUIRE_APPROVAL

    async def allow_sandbox(command: PlannedCommand) -> bool:
        del command
        return True

    return CodingAgentSessionOptions(
        workspace_root=workspace_root,
        model_factory=lambda: model,
        interaction_transport=_UnusedInteractionTransport(),
        command_options=RunCommandsToolOptions(
            shell_executable="/bin/sh",
            environment_builder=FilteredCommandEnvironmentBuilder(
                inherited_environment={},
                allowed_override_keys=frozenset(),
            ),
            permission_evaluator=HostCommandPermissionEvaluator(require_approval),
            approval_resolver=HostCommandApprovalResolver(approval.approve_command),
            sandbox_preflight=HostCommandSandboxPreflight(allow_sandbox),
        ),
        mutation_options=ProductionWorkspaceEditingOptions(approval_callback=approval.approve_patch),
        read_files_external_authorized=False,
        read_files_image_input_supported=False,
    )
