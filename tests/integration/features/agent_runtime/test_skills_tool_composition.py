"""Offline integration coverage for Version 1 skills tool-loop composition."""

import asyncio
import json
from dataclasses import dataclass, field

from fabrica.bootstrap import ActiveSkillCompactionOptions, create_tool_loop_runtime
from fabrica.features.agent_runtime.adapters.inbound.registered_tool import (
    SKILLS_TOOL_NAME,
    SkillActivationToolContext,
    create_skills_registered_tool,
)
from fabrica.features.agent_runtime.application.dtos import (
    ActiveSkillSet,
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    RegisteredSkill,
    SkillDefinition,
    SkillRegistrySnapshot,
    SkillSource,
    SkillTrustBinding,
    SkillTrustDecision,
    SkillTrustDecisionStatus,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCancellationSignal,
    ToolDefinition,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.use_cases import (
    ActivateSkill,
    EvaluateSkillTrust,
    RehydrateActiveSkillContext,
)


def test_skills_registered_tool_composes_into_a_tool_loop_and_returns_structured_activation_content() -> None:
    snapshot = _snapshot()
    skills_tool = create_skills_registered_tool(
        ActivateSkill(EvaluateSkillTrust(_TrustedLookup(), _SnapshotRevisionLoader(snapshot))),
        SkillActivationToolContext(
            workspace_identity="workspace-1",
            run_id="run-1",
            snapshot=snapshot,
            active_skills=ActiveSkillSet(run_id="run-1", registry_snapshot_id=snapshot.snapshot_id),
        ),
    )
    model = _SkillToolModel()
    runtime = create_tool_loop_runtime(model=model, tools=(skills_tool,))

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Review the pull request.")))

    assert tuple(tool.name for tool in runtime.available_tools) == (SKILLS_TOOL_NAME,)
    assert len(result.tool_results) == 1
    content = result.tool_results[0].content
    assert len(content) == 1
    assert isinstance(content[0], ToolTextContent)
    assert json.loads(content[0].text)["instructions"] == "# Review\n"
    assert result.output_text == "activated"


def test_compacted_active_skills_rehydrate_in_order_before_retrieved_context() -> None:
    active_skills = ActiveSkillSet(run_id="run-1", registry_snapshot_id="snapshot-1")
    active_skills.register(skill_id="workspace:first", revision="sha256:" + "a" * 64, instructions="first")
    active_skills.register(skill_id="workspace:second", revision="sha256:" + "b" * 64, instructions="second")
    model = _ContextRecordingModel()
    runtime = create_tool_loop_runtime(
        model=model,
        active_skill_compaction=ActiveSkillCompactionOptions(
            rehydrator=RehydrateActiveSkillContext(max_total_context_chars=100),
            run_id="run-1",
            registry_snapshot_id="snapshot-1",
        ),
    )

    result = asyncio.run(
        runtime.run(
            LocalAgentRunCommand(
                prompt="Continue",
                context=(LocalAgentContextBlock(text="retrieved"),),
            ),
            active_skill_state=RehydrateActiveSkillContext.compact(active_skills),
        )
    )

    assert result.succeeded
    assert [block.text for block in model.commands[0].context] == ["first", "second", "retrieved"]


def test_active_skill_context_overflow_stops_before_the_next_model_turn() -> None:
    active_skills = ActiveSkillSet(run_id="run-1", registry_snapshot_id="snapshot-1")
    active_skills.register(skill_id="workspace:large", revision="sha256:" + "c" * 64, instructions="too large")
    model = _ContextRecordingModel()
    runtime = create_tool_loop_runtime(
        model=model,
        active_skill_compaction=ActiveSkillCompactionOptions(
            rehydrator=RehydrateActiveSkillContext(max_total_context_chars=5),
            run_id="run-1",
            registry_snapshot_id="snapshot-1",
        ),
    )

    result = asyncio.run(
        runtime.run(
            LocalAgentRunCommand(prompt="Continue"),
            active_skill_state=RehydrateActiveSkillContext.compact(active_skills),
        )
    )

    assert result.status.value == "active_skill_context_overflow"
    assert model.commands == []


@dataclass(slots=True)
class _SkillToolModel:
    calls: list[tuple[ToolDefinition, ...]] = field(default_factory=list)

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        del command, cancellation
        self.calls.append(available_tools)
        if not tool_results:
            return ToolAwareModelResponse(
                tool_calls=(
                    ToolCallRequest(call_id="call-1", tool_name=SKILLS_TOOL_NAME, arguments={"skill": "review-pr"}),
                ),
            )
        return ToolAwareModelResponse(output_text="activated")


@dataclass(slots=True)
class _ContextRecordingModel:
    commands: list[LocalAgentRunCommand] = field(default_factory=list)

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        del available_tools, tool_results, cancellation
        self.commands.append(command)
        return ToolAwareModelResponse(output_text="done")


@dataclass(frozen=True, slots=True)
class _TrustedLookup:
    def get_decision(self, binding: SkillTrustBinding) -> SkillTrustDecision:
        return SkillTrustDecision(status=SkillTrustDecisionStatus.TRUSTED, binding=binding)


@dataclass(frozen=True, slots=True)
class _SnapshotRevisionLoader:
    snapshot: SkillRegistrySnapshot

    def load_registered(self, skill: RegisteredSkill) -> SkillDefinition:
        del skill
        return self.snapshot.skills[0].definition


def _snapshot() -> SkillRegistrySnapshot:
    definition = SkillDefinition.from_skill_file_bytes(
        name="review-pr",
        description="Review pull requests.",
        instructions="# Review\n",
        skill_file_bytes=b"review-pr",
    )
    skill = RegisteredSkill(skill_id="workspace:review-pr", source=SkillSource.WORKSPACE, definition=definition)
    return SkillRegistrySnapshot.create(snapshot_id="snapshot-1", skills=(skill,))
