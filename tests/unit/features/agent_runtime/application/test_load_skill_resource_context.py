"""Tests for selected Agent Skill resource context loading orchestration."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillResourceContext,
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    SelectedSkillResource,
    SkillResourceContextBounds,
)
from fabrica.features.agent_runtime.application.ports import SkillContextLoadError
from fabrica.features.agent_runtime.application.use_cases import LoadSkillResourceContext


@dataclass
class FakeSkillResourceContextLoader:
    loaded_by_id: dict[tuple[str, str], LoadedSkillResourceContext]
    calls: list[SelectedSkillResource] = field(default_factory=list)

    def load(self, selection: SelectedSkillResource) -> LoadedSkillResourceContext:
        self.calls.append(selection)
        try:
            return self.loaded_by_id[(selection.skill_id, selection.resource_id)]
        except KeyError as err:
            msg = "selected skill resource is unavailable"
            raise SkillContextLoadError(
                msg,
                skill_id=selection.skill_id,
                category="missing_resource",
                metadata={"resource_id": selection.resource_id},
            ) from err


def test_load_skill_resource_context_returns_deterministic_runtime_context_blocks() -> None:
    first = SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md")
    second = SelectedSkillResource(
        skill_id="hexagonal-architecture",
        resource_id="examples/ports.txt",
        label="Ports Example",
    )
    loader = FakeSkillResourceContextLoader(
        loaded_by_id={
            ("python-testing", "references/example.md"): LoadedSkillResourceContext(
                skill_id="python-testing",
                resource_id="references/example.md",
                text="# Example\n\nUse focused pytest tests.",
                media_type="text/markdown",
                metadata={"file_name": "example.md"},
            ),
            ("hexagonal-architecture", "examples/ports.txt"): LoadedSkillResourceContext(
                skill_id="hexagonal-architecture",
                resource_id="examples/ports.txt",
                label="Ports Example",
                text="Keep adapters outside the core.",
            ),
        },
    )

    context = LoadSkillResourceContext(loader=loader).load((first, second))

    assert context == (
        LocalAgentContextBlock(
            text="# Example\n\nUse focused pytest tests.",
            label="Agent Skill Resource: python-testing/references/example.md",
            metadata={
                "source": "agent_skill_resource",
                "skill_id": "python-testing",
                "resource_id": "references/example.md",
                "media_type": "text/markdown",
                "file_name": "example.md",
            },
        ),
        LocalAgentContextBlock(
            text="Keep adapters outside the core.",
            label="Agent Skill Resource: Ports Example",
            metadata={
                "source": "agent_skill_resource",
                "skill_id": "hexagonal-architecture",
                "resource_id": "examples/ports.txt",
                "media_type": "text/plain",
            },
        ),
    )
    assert loader.calls == [first, second]


def test_load_skill_resource_context_enforces_selected_resource_count_before_loading() -> None:
    loader = FakeSkillResourceContextLoader(loaded_by_id={})
    selections = (
        SelectedSkillResource(skill_id="one", resource_id="a.txt"),
        SelectedSkillResource(skill_id="two", resource_id="b.txt"),
    )

    with pytest.raises(ValueError, match="selected skill resource count"):
        LoadSkillResourceContext(
            loader=loader,
            bounds=SkillResourceContextBounds(max_selected_resources=1),
        ).load(selections)

    assert loader.calls == []


def test_load_skill_resource_context_enforces_per_resource_and_total_bounds() -> None:
    per_resource_loader = FakeSkillResourceContextLoader(
        loaded_by_id={
            ("bounded", "oversized.txt"): LoadedSkillResourceContext(
                skill_id="bounded",
                resource_id="oversized.txt",
                text="x" * 30,
            ),
        },
    )

    with pytest.raises(ValueError, match="per-resource bound"):
        LoadSkillResourceContext(
            loader=per_resource_loader,
            bounds=SkillResourceContextBounds(max_chars_per_resource=20),
        ).load((SelectedSkillResource(skill_id="bounded", resource_id="oversized.txt"),))

    total_loader = FakeSkillResourceContextLoader(
        loaded_by_id={
            ("one", "a.txt"): LoadedSkillResourceContext(skill_id="one", resource_id="a.txt", text="x" * 10),
            ("two", "b.txt"): LoadedSkillResourceContext(skill_id="two", resource_id="b.txt", text="x" * 10),
        },
    )

    with pytest.raises(ValueError, match="total bound"):
        LoadSkillResourceContext(loader=total_loader, bounds=SkillResourceContextBounds(max_total_chars=19)).load(
            (
                SelectedSkillResource(skill_id="one", resource_id="a.txt"),
                SelectedSkillResource(skill_id="two", resource_id="b.txt"),
            ),
        )


def test_load_skill_resource_context_propagates_application_safe_loader_failures() -> None:
    loader = FakeSkillResourceContextLoader(loaded_by_id={})

    with pytest.raises(SkillContextLoadError) as exc_info:
        LoadSkillResourceContext(loader=loader).load(
            (SelectedSkillResource(skill_id="missing", resource_id="notes.txt"),),
        )

    assert exc_info.value.skill_id == "missing"
    assert exc_info.value.category == "missing_resource"
    assert exc_info.value.metadata["resource_id"] == "notes.txt"


def test_augment_command_appends_skill_resource_context_without_running_runtime() -> None:
    existing_context = LocalAgentContextBlock(text="Existing context", label="notes")
    command = LocalAgentRunCommand(
        prompt="Use the provided context.",
        context=(existing_context,),
        model_hint="codex-compatible",
    )
    selection = SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md")
    loader = FakeSkillResourceContextLoader(
        loaded_by_id={
            ("python-testing", "references/example.md"): LoadedSkillResourceContext(
                skill_id="python-testing",
                resource_id="references/example.md",
                text="# Example\n\nUse pytest.",
                media_type="text/markdown",
            ),
        },
    )

    augmented = LoadSkillResourceContext(loader=loader).augment_command(command, (selection,))

    assert augmented.prompt == command.prompt
    assert augmented.model_hint == "codex-compatible"
    assert augmented.context[0] == existing_context
    assert augmented.context[1] == LocalAgentContextBlock(
        text="# Example\n\nUse pytest.",
        label="Agent Skill Resource: python-testing/references/example.md",
        metadata={
            "source": "agent_skill_resource",
            "skill_id": "python-testing",
            "resource_id": "references/example.md",
            "media_type": "text/markdown",
        },
    )
