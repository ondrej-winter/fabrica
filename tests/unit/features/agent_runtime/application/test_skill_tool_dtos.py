"""Tests for selected Agent Skill tool exposure DTO contracts."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_MAX_SELECTED_SKILL_TOOLS,
    DEFAULT_MAX_SKILL_TOOL_REASON_CHARS,
    SelectedSkill,
    SelectedSkillToolDeclaration,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    SkillToolPreparationResult,
    ToolDefinition,
)


def test_skill_tool_status_values_match_normalized_contract() -> None:
    assert {status.value for status in SkillToolExposureStatus} == {
        "registered",
        "skipped",
        "denied",
        "duplicate",
        "invalid_metadata",
        "unknown_selection",
        "script_deferred",
    }


def test_registered_skill_tool_declaration_exposes_tool_definition() -> None:
    tool = ToolDefinition(name="lookup_note", description="Lookup a synthetic note")
    declaration = SelectedSkillToolDeclaration(
        skill_id="python-testing",
        status=SkillToolExposureStatus.REGISTERED,
        tool=tool,
        metadata={"source": "test"},
    )

    assert declaration.display_label == "lookup_note"
    assert declaration.exposes_model_tool is True
    assert SkillToolPreparationResult(declarations=(declaration,)).tool_definitions == (tool,)
    with pytest.raises(FrozenInstanceError):
        declaration.status = SkillToolExposureStatus.DENIED  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError):
        cast("dict[str, object]", declaration.metadata)["source"] = "changed"


def test_script_deferred_declaration_never_exposes_model_tool() -> None:
    declaration = SelectedSkillToolDeclaration(
        skill_id="python-testing",
        status=SkillToolExposureStatus.SCRIPT_DEFERRED,
        label="scripts/check.py",
        reason="script execution requires explicit policy approval",
    )

    assert declaration.display_label == "scripts/check.py"
    assert declaration.exposes_model_tool is False
    assert SkillToolPreparationResult(declarations=(declaration,)).tool_definitions == ()

    with pytest.raises(ValueError, match="must not expose a tool definition"):
        SelectedSkillToolDeclaration(
            skill_id="python-testing",
            status=SkillToolExposureStatus.SCRIPT_DEFERRED,
            tool=ToolDefinition(name="run_script", description="Run script"),
        )


def test_registered_declarations_require_tool_definition() -> None:
    with pytest.raises(ValueError, match="require a tool definition"):
        SelectedSkillToolDeclaration(skill_id="python-testing", status=SkillToolExposureStatus.REGISTERED)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: SelectedSkillToolDeclaration(skill_id="", status=SkillToolExposureStatus.DENIED), "must not be empty"),
        (
            lambda: SelectedSkillToolDeclaration(
                skill_id="python-testing",
                status=SkillToolExposureStatus.DENIED,
                label=" bad",
            ),
            "leading or trailing",
        ),
        (
            lambda: SelectedSkillToolDeclaration(
                skill_id="python-testing",
                status=SkillToolExposureStatus.DENIED,
                reason="x" * (DEFAULT_MAX_SKILL_TOOL_REASON_CHARS + 1),
            ),
            "reason bound",
        ),
    ],
)
def test_skill_tool_declaration_safe_text_fields_are_bounded(factory: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_skill_tool_preparation_command_copies_inputs_and_enforces_bounds() -> None:
    selected_skills = [SelectedSkill(skill_id="python-testing")]
    requested_tools = [
        SelectedSkillToolDeclaration(
            skill_id="python-testing",
            status=SkillToolExposureStatus.REGISTERED,
            tool=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
        ),
    ]

    command = SkillToolPreparationCommand(
        selected_skills=tuple(selected_skills),
        requested_tools=tuple(requested_tools),
    )
    selected_skills.append(SelectedSkill(skill_id="extra"))
    requested_tools.clear()

    assert command.selected_skill_ids == frozenset({"python-testing"})
    assert len(command.requested_tools) == 1
    with pytest.raises(ValueError, match="max_selected_tools must be at least 1"):
        SkillToolPreparationCommand(max_selected_tools=0)
    with pytest.raises(ValueError, match="selected skill tool count"):
        SkillToolPreparationCommand(
            requested_tools=tuple(
                SelectedSkillToolDeclaration(
                    skill_id="python-testing",
                    status=SkillToolExposureStatus.DENIED,
                )
                for _ in range(DEFAULT_MAX_SELECTED_SKILL_TOOLS + 1)
            ),
        )
