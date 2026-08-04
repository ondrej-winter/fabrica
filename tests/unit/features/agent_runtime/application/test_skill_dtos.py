"""Tests for selected Agent Skills context DTO contracts."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS,
    DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS,
    DEFAULT_MAX_SELECTED_SKILL_RESOURCES,
    DEFAULT_MAX_SELECTED_SKILLS,
    DEFAULT_MAX_SKILL_CONTEXT_CHARS,
    DEFAULT_MAX_SKILL_RESOURCE_CONTEXT_CHARS,
    DEFAULT_MAX_TOTAL_SKILL_CONTEXT_CHARS,
    DEFAULT_MAX_TOTAL_SKILL_RESOURCE_CONTEXT_CHARS,
    LoadedSkillContext,
    LoadedSkillResourceContext,
    SelectedSkill,
    SelectedSkillResource,
    SkillContextBounds,
    SkillResourceContextBounds,
)
from fabrica.features.agent_runtime.application.dtos.runtime import MAX_CONTEXT_TEXT_CHARS

EXPECTED_DEFAULT_MAX_SELECTED_SKILLS = 8
EXPECTED_DEFAULT_MAX_SKILL_CONTEXT_CHARS = 8_000
EXPECTED_DEFAULT_MAX_TOTAL_SKILL_CONTEXT_CHARS = 16_000
EXPECTED_DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS = 120
EXPECTED_DEFAULT_MAX_SELECTED_SKILL_RESOURCES = 8
EXPECTED_DEFAULT_MAX_SKILL_RESOURCE_CONTEXT_CHARS = 8_000
EXPECTED_DEFAULT_MAX_TOTAL_SKILL_RESOURCE_CONTEXT_CHARS = 16_000
EXPECTED_DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS = 160


def test_default_skill_context_bounds_are_conservative() -> None:
    bounds = SkillContextBounds()

    assert bounds.max_selected_skills == DEFAULT_MAX_SELECTED_SKILLS == EXPECTED_DEFAULT_MAX_SELECTED_SKILLS
    assert bounds.max_chars_per_skill == DEFAULT_MAX_SKILL_CONTEXT_CHARS == EXPECTED_DEFAULT_MAX_SKILL_CONTEXT_CHARS
    assert (
        bounds.max_total_chars
        == DEFAULT_MAX_TOTAL_SKILL_CONTEXT_CHARS
        == EXPECTED_DEFAULT_MAX_TOTAL_SKILL_CONTEXT_CHARS
    )
    assert bounds.max_label_chars == DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS == EXPECTED_DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS


def test_skill_context_bounds_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="max_selected_skills"):
        SkillContextBounds(max_selected_skills=0)
    with pytest.raises(ValueError, match="max_chars_per_skill"):
        SkillContextBounds(max_chars_per_skill=0)
    with pytest.raises(ValueError, match="context block bound"):
        SkillContextBounds(max_chars_per_skill=MAX_CONTEXT_TEXT_CHARS + 1)
    with pytest.raises(ValueError, match="max_total_chars"):
        SkillContextBounds(max_total_chars=0)
    with pytest.raises(ValueError, match="max_label_chars"):
        SkillContextBounds(max_label_chars=0)


def test_default_skill_resource_context_bounds_are_conservative() -> None:
    bounds = SkillResourceContextBounds()

    assert (
        bounds.max_selected_resources
        == DEFAULT_MAX_SELECTED_SKILL_RESOURCES
        == EXPECTED_DEFAULT_MAX_SELECTED_SKILL_RESOURCES
    )
    assert (
        bounds.max_chars_per_resource
        == DEFAULT_MAX_SKILL_RESOURCE_CONTEXT_CHARS
        == EXPECTED_DEFAULT_MAX_SKILL_RESOURCE_CONTEXT_CHARS
    )
    assert (
        bounds.max_total_chars
        == DEFAULT_MAX_TOTAL_SKILL_RESOURCE_CONTEXT_CHARS
        == EXPECTED_DEFAULT_MAX_TOTAL_SKILL_RESOURCE_CONTEXT_CHARS
    )
    assert (
        bounds.max_label_chars
        == DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS
        == EXPECTED_DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS
    )


def test_skill_resource_context_bounds_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="max_selected_resources"):
        SkillResourceContextBounds(max_selected_resources=0)
    with pytest.raises(ValueError, match="max_chars_per_resource"):
        SkillResourceContextBounds(max_chars_per_resource=0)
    with pytest.raises(ValueError, match="context block bound"):
        SkillResourceContextBounds(max_chars_per_resource=MAX_CONTEXT_TEXT_CHARS + 1)
    with pytest.raises(ValueError, match="max_total_chars"):
        SkillResourceContextBounds(max_total_chars=0)
    with pytest.raises(ValueError, match="max_label_chars"):
        SkillResourceContextBounds(max_label_chars=0)


def test_selected_skill_is_path_free_safe_and_immutable() -> None:
    metadata = {"priority": 1}
    selection = SelectedSkill(skill_id="python-testing", label="Python Testing", metadata=metadata)

    metadata["priority"] = 2

    assert selection.skill_id == "python-testing"
    assert selection.display_label == "Python Testing"
    assert selection.metadata["priority"] == 1
    with pytest.raises(TypeError):
        cast("dict[str, object]", selection.metadata)["priority"] = 3
    with pytest.raises(FrozenInstanceError):
        setattr(selection, "skill_id", "changed")  # noqa: B010


def test_selected_skill_rejects_unsafe_identifiers_and_labels() -> None:
    with pytest.raises(ValueError, match="skill_id must not be empty"):
        SelectedSkill(skill_id="")
    with pytest.raises(ValueError, match="leading or trailing whitespace"):
        SelectedSkill(skill_id=" python-testing")
    with pytest.raises(ValueError, match="unsupported characters"):
        SelectedSkill(skill_id="python:testing")
    with pytest.raises(ValueError, match="safe skill label bound"):
        SelectedSkill(skill_id="x" * (DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS + 1))
    with pytest.raises(ValueError, match="unsupported characters"):
        SelectedSkill(skill_id="python-testing", label="Python\nTesting")


def test_loaded_skill_context_validates_markdown_and_safe_metadata() -> None:
    loaded = LoadedSkillContext(
        skill_id="python-testing",
        label="Python Testing",
        markdown="# Python Testing\n\nUse pytest-native assertions.",
        metadata={"kind": "skill_markdown"},
    )

    assert loaded.display_label == "Python Testing"
    assert loaded.markdown.startswith("# Python Testing")
    assert loaded.metadata["kind"] == "skill_markdown"
    with pytest.raises(TypeError):
        cast("dict[str, object]", loaded.metadata)["kind"] = "changed"


def test_loaded_skill_context_rejects_empty_or_unbounded_markdown() -> None:
    with pytest.raises(ValueError, match="skill markdown must not be empty"):
        LoadedSkillContext(skill_id="empty", markdown="  \n")

    with pytest.raises(ValueError, match="context block bound"):
        LoadedSkillContext(skill_id="oversized", markdown="x" * (MAX_CONTEXT_TEXT_CHARS + 1))


def test_selected_skill_resource_is_path_free_safe_and_immutable() -> None:
    metadata = {"priority": 1}
    selection = SelectedSkillResource(
        skill_id="python-testing",
        resource_id="references/example.md",
        label="Python Testing Example",
        metadata=metadata,
    )

    metadata["priority"] = 2

    assert selection.skill_id == "python-testing"
    assert selection.resource_id == "references/example.md"
    assert selection.display_label == "Python Testing Example"
    assert selection.metadata["priority"] == 1
    with pytest.raises(TypeError):
        cast("dict[str, object]", selection.metadata)["priority"] = 3
    with pytest.raises(FrozenInstanceError):
        setattr(selection, "resource_id", "changed")  # noqa: B010


def test_selected_skill_resource_rejects_unsafe_identifiers_and_labels() -> None:
    with pytest.raises(ValueError, match="resource_id must not be empty"):
        SelectedSkillResource(skill_id="python-testing", resource_id="")
    with pytest.raises(ValueError, match="leading or trailing whitespace"):
        SelectedSkillResource(skill_id="python-testing", resource_id=" references/example.md")
    with pytest.raises(ValueError, match="traversal segments"):
        SelectedSkillResource(skill_id="python-testing", resource_id="../private.txt")
    with pytest.raises(ValueError, match="relative resource identifier"):
        SelectedSkillResource(skill_id="python-testing", resource_id="/private.txt")
    with pytest.raises(ValueError, match="unsupported characters"):
        SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md?raw=1")
    with pytest.raises(ValueError, match="safe skill resource label bound"):
        SelectedSkillResource(
            skill_id="python-testing",
            resource_id="x" * (DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS + 1),
        )


def test_loaded_skill_resource_context_validates_text_and_safe_metadata() -> None:
    loaded = LoadedSkillResourceContext(
        skill_id="python-testing",
        resource_id="references/example.md",
        label="Python Testing Example",
        text="# Example\n\nUse pytest-native assertions.",
        media_type="text/markdown",
        metadata={"kind": "skill_resource"},
    )

    assert loaded.display_label == "Python Testing Example"
    assert loaded.text.startswith("# Example")
    assert loaded.media_type == "text/markdown"
    assert loaded.metadata["kind"] == "skill_resource"
    with pytest.raises(TypeError):
        cast("dict[str, object]", loaded.metadata)["kind"] = "changed"


def test_loaded_skill_resource_context_rejects_empty_or_unbounded_text() -> None:
    with pytest.raises(ValueError, match="skill resource text must not be empty"):
        LoadedSkillResourceContext(skill_id="empty", resource_id="notes.txt", text="  \n")

    with pytest.raises(ValueError, match="context block bound"):
        LoadedSkillResourceContext(
            skill_id="oversized",
            resource_id="notes.txt",
            text="x" * (MAX_CONTEXT_TEXT_CHARS + 1),
        )
