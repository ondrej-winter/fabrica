"""Tests for selected Agent Skills context loading orchestration."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    SelectedSkill,
    SkillContextBounds,
    SkillDefinition,
)
from fabrica.features.agent_runtime.application.ports import SkillDefinitionLoadError
from fabrica.features.agent_runtime.application.use_cases import LoadSkillContext


@dataclass
class FakeSkillDefinitionLoader:
    loaded_by_id: dict[str, SkillDefinition]
    calls: list[SelectedSkill] = field(default_factory=list)

    def load(self, selection: SelectedSkill) -> SkillDefinition:
        self.calls.append(selection)
        try:
            return self.loaded_by_id[selection.skill_id]
        except KeyError as err:
            msg = "selected skill is unavailable"
            raise SkillDefinitionLoadError(
                msg,
                skill_id=selection.skill_id,
                category="missing_skill",
            ) from err


def test_load_skill_context_returns_deterministic_runtime_context_blocks() -> None:
    first = SelectedSkill(skill_id="python-testing")
    second = SelectedSkill(skill_id="hexagonal-architecture", label="Hexagonal Architecture")
    loader = FakeSkillDefinitionLoader(
        loaded_by_id={
            "python-testing": SkillDefinition(
                name="python-testing",
                description="Use focused pytest tests.",
                instructions="# Python Testing\n\nUse focused pytest tests.",
                revision="sha256:" + "a" * 64,
            ),
            "hexagonal-architecture": SkillDefinition(
                name="hexagonal-architecture",
                description="Keep adapters outside the core.",
                instructions="# Hexagonal Architecture\n\nKeep adapters outside the core.",
                revision="sha256:" + "b" * 64,
            ),
        },
    )

    context = LoadSkillContext(loader=loader).load((first, second))

    assert context == (
        LocalAgentContextBlock(
            text="# Python Testing\n\nUse focused pytest tests.",
            label="Agent Skill: python-testing",
            metadata={
                "source": "agent_skill",
                "skill_id": "python-testing",
                "name": "python-testing",
                "description": "Use focused pytest tests.",
                "revision": "sha256:" + "a" * 64,
            },
        ),
        LocalAgentContextBlock(
            text="# Hexagonal Architecture\n\nKeep adapters outside the core.",
            label="Agent Skill: Hexagonal Architecture",
            metadata={
                "source": "agent_skill",
                "skill_id": "hexagonal-architecture",
                "name": "hexagonal-architecture",
                "description": "Keep adapters outside the core.",
                "revision": "sha256:" + "b" * 64,
            },
        ),
    )
    assert loader.calls == [first, second]


def test_load_skill_context_enforces_selected_skill_count_before_loading() -> None:
    loader = FakeSkillDefinitionLoader(loaded_by_id={})
    selections = (
        SelectedSkill(skill_id="one"),
        SelectedSkill(skill_id="two"),
    )

    with pytest.raises(ValueError, match="selected skill count"):
        LoadSkillContext(loader=loader, bounds=SkillContextBounds(max_selected_skills=1)).load(selections)

    assert loader.calls == []


def test_load_skill_context_enforces_per_skill_and_total_bounds() -> None:
    per_skill_loader = FakeSkillDefinitionLoader(
        loaded_by_id={
            "oversized": SkillDefinition(
                name="oversized",
                description="Oversized instructions.",
                instructions="# Oversized\n" + "x" * 30,
                revision="sha256:" + "c" * 64,
            ),
        },
    )

    with pytest.raises(ValueError, match="per-skill bound"):
        LoadSkillContext(
            loader=per_skill_loader,
            bounds=SkillContextBounds(max_chars_per_skill=20),
        ).load((SelectedSkill(skill_id="oversized"),))

    total_loader = FakeSkillDefinitionLoader(
        loaded_by_id={
            "one": SkillDefinition(
                name="one", description="One.", instructions="# One\n" + "x" * 10, revision="sha256:" + "d" * 64
            ),
            "two": SkillDefinition(
                name="two", description="Two.", instructions="# Two\n" + "x" * 10, revision="sha256:" + "e" * 64
            ),
        },
    )

    with pytest.raises(ValueError, match="total bound"):
        LoadSkillContext(loader=total_loader, bounds=SkillContextBounds(max_total_chars=20)).load(
            (SelectedSkill(skill_id="one"), SelectedSkill(skill_id="two")),
        )


def test_load_skill_context_propagates_application_safe_loader_failures() -> None:
    loader = FakeSkillDefinitionLoader(loaded_by_id={})

    with pytest.raises(SkillDefinitionLoadError) as exc_info:
        LoadSkillContext(loader=loader).load((SelectedSkill(skill_id="missing"),))

    assert exc_info.value.skill_id == "missing"
    assert exc_info.value.category == "missing_skill"


def test_augment_command_appends_skill_context_without_running_runtime() -> None:
    existing_context = LocalAgentContextBlock(text="Existing context", label="notes")
    command = LocalAgentRunCommand(
        prompt="Use the provided context.",
        context=(existing_context,),
        model_hint="codex-compatible",
    )
    selection = SelectedSkill(skill_id="python-testing")
    loader = FakeSkillDefinitionLoader(
        loaded_by_id={
            "python-testing": SkillDefinition(
                name="python-testing",
                description="Use pytest.",
                instructions="# Python Testing\n\nUse pytest.",
                revision="sha256:" + "f" * 64,
            ),
        },
    )

    augmented = LoadSkillContext(loader=loader).augment_command(command, (selection,))

    assert augmented.prompt == command.prompt
    assert augmented.model_hint == "codex-compatible"
    assert augmented.context[0] == existing_context
    assert augmented.context[1] == LocalAgentContextBlock(
        text="# Python Testing\n\nUse pytest.",
        label="Agent Skill: python-testing",
        metadata={
            "source": "agent_skill",
            "skill_id": "python-testing",
            "name": "python-testing",
            "description": "Use pytest.",
            "revision": "sha256:" + "f" * 64,
        },
    )
