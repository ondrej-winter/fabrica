"""Offline integration tests for Agent Skill context runtime composition."""

from pathlib import Path

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


def test_skill_augmented_command_composition_loads_selected_skills_in_order(tmp_path: Path) -> None:
    _write_skill(tmp_path, "python-testing", "# Python Testing\n\nUse focused pytest tests.")
    _write_skill(tmp_path, "hexagonal-architecture", "# Hexagonal Architecture\n\nKeep adapters outside the core.")
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
    assert augmented.context == (
        LocalAgentContextBlock(text="Existing context", label="notes"),
        LocalAgentContextBlock(
            text="# Python Testing\n\nUse focused pytest tests.",
            label="Agent Skill: python-testing",
            metadata={"source": "agent_skill", "skill_id": "python-testing", "heading": "Python Testing"},
        ),
        LocalAgentContextBlock(
            text="# Hexagonal Architecture\n\nKeep adapters outside the core.",
            label="Agent Skill: Hexagonal Architecture",
            metadata={
                "source": "agent_skill",
                "skill_id": "hexagonal-architecture",
                "heading": "Hexagonal Architecture",
            },
        ),
    )


def test_skill_context_loader_composition_keeps_script_references_inert(tmp_path: Path) -> None:
    markdown = "# Script Reference\n\nRun `./scripts/setup.sh` only after a future approval policy exists."
    _write_skill(tmp_path, "script-reference", markdown)

    context_blocks = create_skill_context_loader(skill_roots=(tmp_path,)).load(
        (SelectedSkill(skill_id="script-reference"),),
    )

    assert context_blocks == (
        LocalAgentContextBlock(
            text=markdown,
            label="Agent Skill: script-reference",
            metadata={"source": "agent_skill", "skill_id": "script-reference", "heading": "Script Reference"},
        ),
    )


def test_skill_context_composition_accepts_bounds_and_privacy_defaults(tmp_path: Path) -> None:
    _write_skill(tmp_path, "bounded", "# Bounded\n\nSmall content.")

    augmented = create_skill_augmented_local_agent_command(
        LocalAgentRunCommand(prompt="Use bounded context."),
        (SelectedSkill(skill_id="bounded"),),
        skill_roots=(tmp_path,),
        bounds=SkillContextBounds(max_selected_skills=1, max_chars_per_skill=100, max_total_chars=100),
    )

    assert len(augmented.context) == 1
    assert augmented.context[0].metadata["heading"] == "Bounded"


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
    assert augmented.context[0].metadata["heading"] == "Python Testing"
    assert augmented.context[1].metadata["resource_id"] == "references/example.md"


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
