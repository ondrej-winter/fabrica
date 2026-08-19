"""Tests for the read-only Agent Skill markdown file adapter."""

from pathlib import Path

import pytest

from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import (
    SkillMarkdownFileContextLoader,
    SkillResourceFileContextLoader,
)
from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillContext,
    LoadedSkillResourceContext,
    SelectedSkill,
    SelectedSkillResource,
)
from fabrica.features.agent_runtime.application.ports import SkillContextLoadError
from tests.synthetic_values import PRIVATE_FILE_CONTENT

SYNTHETIC_SECRET = PRIVATE_FILE_CONTENT


def test_load_returns_loaded_skill_context_from_selected_skill_directory(tmp_path: Path) -> None:
    skill_file = _write_skill(tmp_path, "python-testing", "# Python Testing\n\nUse pytest.")

    loaded = SkillMarkdownFileContextLoader(skill_roots=(tmp_path,)).load(
        SelectedSkill(skill_id="python-testing", label="Python Testing", metadata={"ignored": "selection"}),
    )

    assert skill_file.read_text(encoding="utf-8") == "# Python Testing\n\nUse pytest."
    assert loaded == LoadedSkillContext(
        skill_id="python-testing",
        label="Python Testing",
        markdown="# Python Testing\n\nUse pytest.",
        metadata={"heading": "Python Testing"},
    )


def test_load_searches_configured_skill_roots_in_order(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write_skill(second_root, "hexagonal-architecture", "# Hexagonal Architecture\n\nKeep boundaries.")

    loaded = SkillMarkdownFileContextLoader(skill_roots=(first_root, second_root)).load(
        SelectedSkill(skill_id="hexagonal-architecture"),
    )

    assert loaded.markdown == "# Hexagonal Architecture\n\nKeep boundaries."
    assert loaded.metadata["heading"] == "Hexagonal Architecture"


def test_load_treats_script_references_as_inert_markdown_text(tmp_path: Path) -> None:
    markdown = "# Script Reference\n\nRun `./scripts/setup.sh` if approved later."
    _write_skill(tmp_path, "script-reference", markdown)

    loaded = SkillMarkdownFileContextLoader(skill_roots=(tmp_path,)).load(
        SelectedSkill(skill_id="script-reference"),
    )

    assert loaded.markdown == markdown


def test_load_raises_safe_missing_skill_error_without_private_path(tmp_path: Path) -> None:
    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillMarkdownFileContextLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="missing"))

    assert exc_info.value.skill_id == "missing"
    assert exc_info.value.category == "missing_skill"
    assert "path" not in exc_info.value.metadata
    assert str(tmp_path) not in str(exc_info.value)


def test_load_can_include_verbose_path_diagnostics_when_enabled(tmp_path: Path) -> None:
    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillMarkdownFileContextLoader(skill_roots=(tmp_path,), verbose_diagnostics=True).load(
            SelectedSkill(skill_id="missing"),
        )

    assert exc_info.value.category == "missing_skill"
    assert exc_info.value.metadata == {"diagnostic_mode": "verbose"}


def test_load_rejects_directory_where_skill_file_should_be(tmp_path: Path) -> None:
    skill_file_directory = tmp_path / "directory-shape" / "SKILL.md"
    skill_file_directory.mkdir(parents=True)

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillMarkdownFileContextLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="directory-shape"))

    assert exc_info.value.category == "invalid_skill_file"


def test_load_rejects_invalid_utf8_markdown(tmp_path: Path) -> None:
    skill_file = tmp_path / "invalid-utf8" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_bytes(b"\xff\xfe")

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillMarkdownFileContextLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="invalid-utf8"))

    assert exc_info.value.category == "decode_error"


@pytest.mark.parametrize(
    "markdown",
    ["", "   \n\t", "## Not Top Level\n\nBody only."],
)
def test_load_rejects_empty_or_headingless_markdown(tmp_path: Path, markdown: str) -> None:
    _write_skill(tmp_path, "invalid-markdown", markdown)

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillMarkdownFileContextLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="invalid-markdown"))

    assert exc_info.value.category == "invalid_skill_markdown"


def test_load_rejects_path_traversal_without_exposing_file_contents(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    skill_root = tmp_path / "skills"
    _write_skill(private_root, "escaped", f"# Escaped\n\n{SYNTHETIC_SECRET}")

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillMarkdownFileContextLoader(skill_roots=(skill_root,)).load(SelectedSkill(skill_id="../private/escaped"))

    assert exc_info.value.category == "invalid_skill_path"
    assert SYNTHETIC_SECRET not in str(exc_info.value)
    assert SYNTHETIC_SECRET not in str(exc_info.value.metadata)


def test_load_resource_returns_loaded_text_resource_from_selected_skill_directory(tmp_path: Path) -> None:
    resource_file = _write_resource(tmp_path, "python-testing", "references/example.md", "# Example\n\nUse pytest.")

    loaded = SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
        SelectedSkillResource(
            skill_id="python-testing",
            resource_id="references/example.md",
            label="Python Testing Example",
            metadata={"ignored": "selection"},
        ),
    )

    assert resource_file.read_text(encoding="utf-8") == "# Example\n\nUse pytest."
    assert loaded == LoadedSkillResourceContext(
        skill_id="python-testing",
        resource_id="references/example.md",
        label="Python Testing Example",
        text="# Example\n\nUse pytest.",
        media_type="text/markdown",
        metadata={"file_name": "example.md"},
    )


def test_load_resource_searches_configured_skill_roots_in_order(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write_resource(second_root, "python-testing", "data/example.json", '{"ok": true}')

    loaded = SkillResourceFileContextLoader(skill_roots=(first_root, second_root)).load(
        SelectedSkillResource(skill_id="python-testing", resource_id="data/example.json"),
    )

    assert loaded.text == '{"ok": true}'
    assert loaded.media_type == "application/json"
    assert loaded.metadata["file_name"] == "example.json"


def test_load_resource_treats_script_references_as_inert_text(tmp_path: Path) -> None:
    text = "Run `./scripts/setup.sh` only after a future approval policy exists."
    _write_resource(tmp_path, "script-reference", "notes.txt", text)

    loaded = SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
        SelectedSkillResource(skill_id="script-reference", resource_id="notes.txt"),
    )

    assert loaded.text == text


def test_load_resource_raises_safe_missing_resource_error_without_private_path(tmp_path: Path) -> None:
    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
            SelectedSkillResource(skill_id="missing", resource_id="notes.txt"),
        )

    assert exc_info.value.skill_id == "missing"
    assert exc_info.value.category == "missing_resource"
    assert exc_info.value.metadata == {"diagnostic_mode": "safe", "resource_id": "notes.txt"}
    assert str(tmp_path) not in str(exc_info.value)


def test_load_resource_can_include_verbose_path_diagnostics_when_enabled(tmp_path: Path) -> None:
    _write_resource(tmp_path, "invalid", "run.sh", "echo unsafe")

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(tmp_path,), verbose_diagnostics=True).load(
            SelectedSkillResource(skill_id="invalid", resource_id="run.sh"),
        )

    assert exc_info.value.category == "unsupported_resource_type"
    assert exc_info.value.metadata["diagnostic_mode"] == "verbose"
    assert exc_info.value.metadata["resource_id"] == "run.sh"
    assert isinstance(exc_info.value.metadata["path"], str)
    assert exc_info.value.metadata["path"].endswith("invalid/run.sh")


def test_load_resource_rejects_directory_where_resource_should_be(tmp_path: Path) -> None:
    resource_directory = tmp_path / "directory-shape" / "notes.txt"
    resource_directory.mkdir(parents=True)

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
            SelectedSkillResource(skill_id="directory-shape", resource_id="notes.txt"),
        )

    assert exc_info.value.category == "invalid_resource_file"


def test_load_resource_rejects_invalid_utf8_text(tmp_path: Path) -> None:
    resource_file = tmp_path / "invalid-utf8" / "notes.txt"
    resource_file.parent.mkdir(parents=True)
    resource_file.write_bytes(b"\xff\xfe")

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
            SelectedSkillResource(skill_id="invalid-utf8", resource_id="notes.txt"),
        )

    assert exc_info.value.category == "decode_error"


def test_load_resource_rejects_empty_text(tmp_path: Path) -> None:
    _write_resource(tmp_path, "empty", "notes.txt", " \n\t")

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
            SelectedSkillResource(skill_id="empty", resource_id="notes.txt"),
        )

    assert exc_info.value.category == "invalid_resource_text"


@pytest.mark.parametrize("resource_id", ["SKILL.md", "scripts/setup.sh", "binary.bin"])
def test_load_resource_rejects_skill_markdown_and_script_or_binary_file_types(tmp_path: Path, resource_id: str) -> None:
    _write_resource(tmp_path, "unsupported", resource_id, "inert text")

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
            SelectedSkillResource(skill_id="unsupported", resource_id=resource_id),
        )

    assert exc_info.value.category == "unsupported_resource_type"


def test_load_resource_rejects_path_traversal_without_exposing_file_contents(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    skill_root = tmp_path / "skills"
    _write_resource(private_root, "escaped", "secret.txt", SYNTHETIC_SECRET)

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(skill_root,)).load(
            SelectedSkillResource(skill_id="../private/escaped", resource_id="secret.txt"),
        )

    assert exc_info.value.category == "invalid_resource_path"
    assert SYNTHETIC_SECRET not in str(exc_info.value)
    assert SYNTHETIC_SECRET not in str(exc_info.value.metadata)


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
