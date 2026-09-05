"""Offline integration tests for Agent Skill context runtime composition."""

from pathlib import Path

import pytest

from fabrica.bootstrap import (
    SkillContextAugmentationOptions,
    create_skill_augmented_local_agent_command,
    create_skill_context_augmented_local_agent_command,
    create_skill_context_loader,
    create_skill_resource_context_loader,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    SelectedSkill,
    SelectedSkillResource,
    SkillContextBounds,
    SkillResourceContextBounds,
)
from fabrica.features.agent_runtime.application.ports import SkillDefinitionLoadError


def test_skill_augmented_command_composition_loads_selected_skills_in_order(tmp_path: Path) -> None:
    _write_skill(tmp_path, "python-testing", "Use focused pytest tests.")
    _write_skill(tmp_path, "hexagonal-architecture", "Keep adapters outside the core.")
    command = LocalAgentRunCommand(
        prompt="Use the selected skills.",
        context=(LocalAgentContextBlock(text="Existing context", label="notes"),),
        model_hint="codex-compatible",
    )

    augmented = create_skill_augmented_local_agent_command(
        command,
        (
            SelectedSkill(skill_id="python-testing"),
            SelectedSkill(skill_id="hexagonal-architecture", label="Hexagonal Architecture"),
        ),
        skill_roots=(tmp_path,),
    )

    assert augmented.prompt == command.prompt
    assert augmented.model_hint == "codex-compatible"
    assert augmented.context[0] == LocalAgentContextBlock(text="Existing context", label="notes")
    assert [block.text for block in augmented.context[1:]] == [
        "Use focused pytest tests.",
        "Keep adapters outside the core.",
    ]
    assert [block.label for block in augmented.context[1:]] == [
        "Agent Skill: python-testing",
        "Agent Skill: Hexagonal Architecture",
    ]
    assert [block.metadata["name"] for block in augmented.context[1:]] == ["python-testing", "hexagonal-architecture"]
    assert all(str(block.metadata["revision"]).startswith("sha256:") for block in augmented.context[1:])


def test_skill_context_loader_composition_keeps_script_references_inert(tmp_path: Path) -> None:
    instructions = "# Script Reference\n\nRun `./scripts/setup.sh` only after a future approval policy exists."
    _write_skill(tmp_path, "script-reference", instructions)

    context_blocks = create_skill_context_loader(skill_roots=(tmp_path,)).load(
        (SelectedSkill(skill_id="script-reference"),),
    )

    assert context_blocks[0].text == instructions
    assert context_blocks[0].label == "Agent Skill: script-reference"
    assert context_blocks[0].metadata["name"] == "script-reference"
    assert str(context_blocks[0].metadata["revision"]).startswith("sha256:")


def test_skill_context_composition_accepts_bounds_and_privacy_defaults(tmp_path: Path) -> None:
    _write_skill(tmp_path, "bounded", "# Bounded\n\nSmall content.")

    augmented = create_skill_augmented_local_agent_command(
        LocalAgentRunCommand(prompt="Use bounded context."),
        (SelectedSkill(skill_id="bounded"),),
        skill_roots=(tmp_path,),
        bounds=SkillContextBounds(max_selected_skills=1, max_chars_per_skill=100, max_total_chars=100),
    )

    assert len(augmented.context) == 1
    assert augmented.context[0].metadata["name"] == "bounded"


def test_skill_context_composition_rejects_legacy_heading_only_skill_files(tmp_path: Path) -> None:
    skill_file = tmp_path / "legacy" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("# Legacy\n\nHeading-only skill.", encoding="utf-8")

    with pytest.raises(SkillDefinitionLoadError, match="YAML frontmatter") as exc_info:
        create_skill_context_loader(skill_roots=(tmp_path,)).load((SelectedSkill(skill_id="legacy"),))

    assert exc_info.value.category == "invalid_frontmatter"


def test_skill_resource_context_loader_composition_loads_selected_resources_in_order(tmp_path: Path) -> None:
    _write_resource(tmp_path, "python-testing", "references/example.md", "# Example\n\nUse pytest tests.")
    _write_resource(tmp_path, "python-testing", "data/config.yaml", "enabled: true")

    context_blocks = create_skill_resource_context_loader(skill_roots=(tmp_path,)).load(
        (
            SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md"),
            SelectedSkillResource(skill_id="python-testing", resource_id="data/config.yaml", label="Config Example"),
        ),
    )

    assert context_blocks == (
        LocalAgentContextBlock(
            text="# Example\n\nUse pytest tests.",
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
            text="enabled: true",
            label="Agent Skill Resource: Config Example",
            metadata={
                "source": "agent_skill_resource",
                "skill_id": "python-testing",
                "resource_id": "data/config.yaml",
                "media_type": "application/yaml",
                "file_name": "config.yaml",
            },
        ),
    )


def test_combined_skill_context_composition_loads_markdown_then_resources(tmp_path: Path) -> None:
    _write_skill(tmp_path, "python-testing", "# Python Testing\n\nUse focused pytest tests.")
    _write_resource(tmp_path, "python-testing", "references/example.md", "# Example\n\nUse pytest tests.")

    augmented = create_skill_context_augmented_local_agent_command(
        LocalAgentRunCommand(prompt="Use selected context."),
        SkillContextAugmentationOptions(
            skill_selections=(SelectedSkill(skill_id="python-testing"),),
            resource_selections=(
                SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md"),
            ),
            skill_roots=(tmp_path,),
            skill_bounds=SkillContextBounds(max_selected_skills=1, max_chars_per_skill=100, max_total_chars=100),
            resource_bounds=SkillResourceContextBounds(
                max_selected_resources=1,
                max_chars_per_resource=100,
                max_total_chars=100,
            ),
        ),
    )

    assert [block.metadata["source"] for block in augmented.context] == ["agent_skill", "agent_skill_resource"]
    assert augmented.context[0].metadata["name"] == "python-testing"
    assert augmented.context[1].metadata["resource_id"] == "references/example.md"


def _write_skill(root: Path, skill_id: str, instructions: str) -> Path:
    skill_file = root / skill_id / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    description = instructions.splitlines()[0].removeprefix("# ").strip()
    skill_file.write_text(
        f"---\nname: {skill_id}\ndescription: {description}\n---\n\n{instructions}",
        encoding="utf-8",
    )
    return skill_file


def _write_resource(root: Path, skill_id: str, resource_id: str, text: str) -> Path:
    resource_file = root / skill_id / resource_id
    resource_file.parent.mkdir(parents=True, exist_ok=True)
    resource_file.write_text(text, encoding="utf-8")
    return resource_file
