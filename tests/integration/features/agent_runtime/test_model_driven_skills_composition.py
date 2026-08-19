"""Offline integration tests for model-driven selected Agent Skills composition."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

from fabrica.bootstrap import (
    ModelDrivenSkillRuntimeOptions,
    SkillContextAugmentationOptions,
    create_model_driven_skill_runtime,
    create_pydantic_ai_model_driven_skill_runtime,
)
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import PydanticAIToolAwareTurnRequest
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import (
    RegisteredTool,
    SkillAssociatedRegisteredTool,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SafeRuntimeMetadataValue,
    SelectedSkill,
    SelectedSkillResource,
    SelectedSkillToolDeclaration,
    SkillToolExposureStatus,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunStatus,
)

EXPECTED_TOOL_LOOP_TURN_COUNT = 2


@dataclass
class SyntheticSkillToolAwareModel:
    """Fake model that verifies selected skill context before requesting a tool."""

    calls: list[tuple[LocalAgentRunCommand, tuple[ToolDefinition, ...], tuple[ToolCallResult, ...]]] = field(
        default_factory=list,
    )

    def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
    ) -> ToolAwareModelResponse:
        self.calls.append((command, available_tools, tool_results))
        assert [block.metadata["source"] for block in command.context] == ["agent_skill", "agent_skill_resource"]
        if not tool_results:
            return ToolAwareModelResponse(
                tool_calls=(ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"note_id": "abc"}),),
            )
        return ToolAwareModelResponse(output_text=f"final:{tool_results[0].result_text}")


@dataclass
class SyntheticPydanticAISkillTurn:
    """Fake PydanticAI-shaped turn runner for selected skill tool proofs."""

    calls: list[PydanticAIToolAwareTurnRequest] = field(default_factory=list)

    def run_turn(self, request: PydanticAIToolAwareTurnRequest) -> ModelResponse:
        self.calls.append(request)
        assert "Agent Skill: Python Testing" in request.prompt
        assert "Agent Skill Resource: Python Testing Example" in request.prompt
        if not request.tool_results:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="lookup_note", args={"note_id": "abc"}, tool_call_id="call-1")],
            )
        return ModelResponse(parts=[TextPart(f"final:{request.tool_results[0].result_text}")])


def test_model_driven_skill_runtime_combines_selected_context_and_explicit_skill_tool(tmp_path: Path) -> None:
    _write_skill(tmp_path, "python-testing", "# Python Testing\n\nUse focused pytest tests.")
    _write_resource(tmp_path, "python-testing", "references/example.md", "# Example\n\nUse pytest tests.")
    model = SyntheticSkillToolAwareModel()
    skill_tool = _skill_lookup_tool("python-testing")

    runtime = create_model_driven_skill_runtime(
        model=model,
        options=ModelDrivenSkillRuntimeOptions(
            skill_context_options=SkillContextAugmentationOptions(
                skill_selections=(SelectedSkill(skill_id="python-testing", label="Python Testing"),),
                resource_selections=(
                    SelectedSkillResource(
                        skill_id="python-testing",
                        resource_id="references/example.md",
                        label="Python Testing Example",
                    ),
                ),
                skill_roots=(tmp_path,),
            ),
            skill_tools=(skill_tool,),
            limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=100),
        ),
    )

    result = runtime.run(LocalAgentRunCommand(prompt="Use selected skills and tools."))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "final:note:abc"
    assert runtime.available_tools == (skill_tool.registered_tool.definition,)
    assert runtime.tool_preparation.declarations[0].status is SkillToolExposureStatus.REGISTERED
    assert len(model.calls) == EXPECTED_TOOL_LOOP_TURN_COUNT
    assert model.calls[0][0].context[0].metadata["skill_id"] == "python-testing"
    assert model.calls[0][0].context[1].metadata["resource_id"] == "references/example.md"


def test_pydantic_ai_model_driven_skill_runtime_uses_selected_context_and_tool(tmp_path: Path) -> None:
    _write_skill(tmp_path, "python-testing", "# Python Testing\n\nUse focused pytest tests.")
    _write_resource(tmp_path, "python-testing", "references/example.md", "# Example\n\nUse pytest tests.")
    turn = SyntheticPydanticAISkillTurn()
    skill_tool = _skill_lookup_tool("python-testing")

    runtime = create_pydantic_ai_model_driven_skill_runtime(
        turn_runner=turn,
        options=ModelDrivenSkillRuntimeOptions(
            skill_context_options=SkillContextAugmentationOptions(
                skill_selections=(SelectedSkill(skill_id="python-testing", label="Python Testing"),),
                resource_selections=(
                    SelectedSkillResource(
                        skill_id="python-testing",
                        resource_id="references/example.md",
                        label="Python Testing Example",
                    ),
                ),
                skill_roots=(tmp_path,),
            ),
            skill_tools=(skill_tool,),
            limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=100),
        ),
    )

    result = runtime.run(LocalAgentRunCommand(prompt="Use selected skills and tools.", model_hint="synthetic-codex"))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "final:note:abc"
    assert len(turn.calls) == EXPECTED_TOOL_LOOP_TURN_COUNT
    assert turn.calls[0].model_hint == "synthetic-codex"
    assert turn.calls[0].available_tools == (skill_tool.registered_tool.definition,)
    assert turn.calls[1].tool_results == result.tool_results


def test_model_driven_skill_runtime_construction_is_side_effect_free(tmp_path: Path) -> None:
    model = SyntheticSkillToolAwareModel()
    called = False

    def synthetic_tool(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        nonlocal called
        called = True
        return "called"

    runtime = create_model_driven_skill_runtime(
        model=model,
        options=ModelDrivenSkillRuntimeOptions(
            skill_context_options=SkillContextAugmentationOptions(
                skill_selections=(SelectedSkill(skill_id="not-created"),),
                skill_roots=(tmp_path,),
            ),
            skill_tools=(
                SkillAssociatedRegisteredTool(
                    skill_id="not-created",
                    registered_tool=RegisteredTool(
                        definition=ToolDefinition(name="synthetic_tool", description="Synthetic tool"),
                        handler=synthetic_tool,
                    ),
                ),
            ),
        ),
    )

    assert runtime.available_tools == (ToolDefinition(name="synthetic_tool", description="Synthetic tool"),)
    assert model.calls == []
    assert called is False


def test_model_driven_skill_runtime_does_not_expose_unselected_or_script_deferred_tools() -> None:
    selected_tool = _skill_lookup_tool("python-testing")
    unselected_tool = _skill_lookup_tool("private-skill")
    script_deferred = SelectedSkillToolDeclaration(
        skill_id="python-testing",
        status=SkillToolExposureStatus.SCRIPT_DEFERRED,
        label="scripts/check.py",
        reason="scripts are not model-callable in this cut",
    )

    runtime = create_model_driven_skill_runtime(
        model=SyntheticSkillToolAwareModel(),
        options=ModelDrivenSkillRuntimeOptions(
            skill_context_options=SkillContextAugmentationOptions(
                skill_selections=(SelectedSkill(skill_id="python-testing"),),
            ),
            skill_tools=(selected_tool, unselected_tool),
        ),
    )

    declarations = (*runtime.tool_preparation.declarations, script_deferred)

    assert runtime.available_tools == (selected_tool.registered_tool.definition,)
    assert runtime.registered_tools == (selected_tool.registered_tool,)
    assert declarations[1].status is SkillToolExposureStatus.UNKNOWN_SELECTION
    assert script_deferred.exposes_model_tool is False
    assert script_deferred.tool is None


def test_model_driven_skill_runtime_rejects_explicit_zero_tool_limit() -> None:
    """Keep explicit invalid composition limits from being replaced by defaults."""
    with pytest.raises(ValueError, match="max_selected_tools must be at least 1"):
        create_model_driven_skill_runtime(
            model=SyntheticSkillToolAwareModel(),
            options=ModelDrivenSkillRuntimeOptions(
                skill_context_options=SkillContextAugmentationOptions(
                    skill_selections=(SelectedSkill(skill_id="python-testing"),),
                ),
                max_selected_tools=0,
            ),
        )


def _skill_lookup_tool(skill_id: str) -> SkillAssociatedRegisteredTool:
    return SkillAssociatedRegisteredTool(
        skill_id=skill_id,
        registered_tool=RegisteredTool(
            definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
            handler=_lookup_note,
        ),
        label="Lookup Note",
        metadata={"source": "test"},
    )


def _lookup_note(arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    note_id = arguments.get("note_id")
    if not isinstance(note_id, str):
        msg = "note_id must be a string"
        raise TypeError(msg)
    return f"note:{note_id}"


def _write_skill(root: Path, skill_id: str, markdown: str) -> Path:
    skill_file = root / skill_id / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(markdown, encoding="utf-8")
    return skill_file


def _write_resource(root: Path, skill_id: str, resource_id: str, text: str) -> Path:
    resource_file = root / skill_id / resource_id
    resource_file.parent.mkdir(parents=True, exist_ok=True)
    resource_file.write_text(text, encoding="utf-8")
    return resource_file
