"""Tests for selected Agent Skill tool preparation orchestration."""

from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    RuntimeObservation,
    SelectedSkill,
    SelectedSkillToolDeclaration,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    SkillToolPreparationResult,
    ToolDefinition,
)
from fabrica.features.agent_runtime.application.ports import SkillToolPreparationError
from fabrica.features.agent_runtime.application.use_cases import PrepareSkillTools


@dataclass
class FakeSkillToolPreparer:
    result: SkillToolPreparationResult
    calls: list[SkillToolPreparationCommand] = field(default_factory=list)

    def prepare(self, command: SkillToolPreparationCommand) -> SkillToolPreparationResult:
        self.calls.append(command)
        return self.result


class FailingSkillToolPreparer:
    def prepare(self, command: SkillToolPreparationCommand) -> SkillToolPreparationResult:
        del command
        msg = "synthetic failure"
        raise SkillToolPreparationError(
            msg,
            category="adapter_unavailable",
            metadata={"component": "fake"},
        )


def test_prepare_skill_tools_returns_registered_definitions_for_selected_skills() -> None:
    command = SkillToolPreparationCommand(selected_skills=(SelectedSkill(skill_id="python-testing"),))
    declaration = SelectedSkillToolDeclaration(
        skill_id="python-testing",
        status=SkillToolExposureStatus.REGISTERED,
        tool=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
    )
    preparer = FakeSkillToolPreparer(result=SkillToolPreparationResult(declarations=(declaration,)))

    result = PrepareSkillTools(preparer).prepare(command)

    assert result.declarations == (declaration,)
    assert result.tool_definitions == (declaration.tool,)
    assert preparer.calls == [command]


def test_prepare_skill_tools_marks_unknown_skill_declarations_fail_closed() -> None:
    unknown_declaration = SelectedSkillToolDeclaration(
        skill_id="unselected",
        status=SkillToolExposureStatus.REGISTERED,
        tool=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
    )
    preparer = FakeSkillToolPreparer(result=SkillToolPreparationResult(declarations=(unknown_declaration,)))

    result = PrepareSkillTools(preparer).prepare(
        SkillToolPreparationCommand(selected_skills=(SelectedSkill(skill_id="python-testing"),)),
    )

    assert result.declarations[0].status is SkillToolExposureStatus.UNKNOWN_SELECTION
    assert result.declarations[0].tool is None
    assert result.declarations[0].reason == "skill was not explicitly selected"
    assert result.tool_definitions == ()


def test_prepare_skill_tools_marks_duplicate_tool_names_fail_closed() -> None:
    first = SelectedSkillToolDeclaration(
        skill_id="python-testing",
        status=SkillToolExposureStatus.REGISTERED,
        tool=ToolDefinition(name="lookup_note", description="Lookup note from first skill"),
    )
    second = SelectedSkillToolDeclaration(
        skill_id="hexagonal-architecture",
        status=SkillToolExposureStatus.REGISTERED,
        tool=ToolDefinition(name="lookup_note", description="Lookup note from second skill"),
    )
    preparer = FakeSkillToolPreparer(result=SkillToolPreparationResult(declarations=(first, second)))

    result = PrepareSkillTools(preparer).prepare(
        SkillToolPreparationCommand(
            selected_skills=(
                SelectedSkill(skill_id="python-testing"),
                SelectedSkill(skill_id="hexagonal-architecture"),
            ),
        ),
    )

    assert result.declarations[0].status is SkillToolExposureStatus.REGISTERED
    assert result.declarations[1].status is SkillToolExposureStatus.DUPLICATE
    assert result.declarations[1].tool is None
    assert result.tool_definitions == (first.tool,)


def test_prepare_skill_tools_reports_script_deferred_without_exposing_tool() -> None:
    script_deferred = SelectedSkillToolDeclaration(
        skill_id="python-testing",
        status=SkillToolExposureStatus.SCRIPT_DEFERRED,
        label="scripts/check.py",
        reason="scripts are not model-callable in this phase",
    )
    preparer = FakeSkillToolPreparer(result=SkillToolPreparationResult(declarations=(script_deferred,)))

    result = PrepareSkillTools(preparer).prepare(
        SkillToolPreparationCommand(selected_skills=(SelectedSkill(skill_id="python-testing"),)),
    )

    assert result.declarations == (script_deferred,)
    assert result.tool_definitions == ()
    assert result.observations == (
        RuntimeObservation(
            message="selected skill script was not exposed as a model-callable tool",
            metadata={"skill_id": "python-testing", "status": "script_deferred"},
        ),
    )


def test_prepare_skill_tools_normalizes_adapter_errors_to_observations() -> None:
    result = PrepareSkillTools(FailingSkillToolPreparer()).prepare(
        SkillToolPreparationCommand(selected_skills=(SelectedSkill(skill_id="python-testing"),)),
    )

    assert result.declarations == ()
    assert result.tool_definitions == ()
    assert result.observations == (
        RuntimeObservation(
            message="skill tool preparation adapter failed",
            metadata={"category": "adapter_unavailable", "component": "fake"},
        ),
    )
