"""Tests for the read-only Agent Skill markdown file adapter."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import (
    SkillResourceFileContextLoader,
)
from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import adapter as markdown_adapter
from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillResourceContext,
    SelectedSkillResource,
)
from fabrica.features.agent_runtime.application.ports import SkillContextLoadError
from tests.support.sentinels import PRIVATE_FILE_CONTENT

SYNTHETIC_SECRET = PRIVATE_FILE_CONTENT


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


def test_resource_helpers_reject_absolute_skill_and_resource_paths() -> None:
    with pytest.raises(SkillContextLoadError, match="skill path must be relative"):
        markdown_adapter._skill_relative_path_from_id("/private")  # noqa: SLF001
    with pytest.raises(SkillContextLoadError, match="resource path must be relative"):
        markdown_adapter._resource_relative_path(  # noqa: SLF001
            SimpleNamespace(skill_id="skill", resource_id="/private"),  # ty: ignore[invalid-argument-type]
        )


def test_load_resource_rejects_symlinked_skill_directory_outside_root(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    _write_resource(private_root, "escaped", "notes.txt", "private")
    skill_root = tmp_path / "skills"
    linked_private_root = skill_root / "linked-private"
    linked_private_root.parent.mkdir(parents=True)
    linked_private_root.symlink_to(private_root, target_is_directory=True)

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(skill_root,)).load(
            SelectedSkillResource(skill_id="linked-private/escaped", resource_id="notes.txt"),
        )

    assert exc_info.value.category == "invalid_resource_path"


def test_load_resource_rejects_symlinked_resource_outside_skill_directory(tmp_path: Path) -> None:
    private_file = tmp_path / "private.txt"
    private_file.write_text("private", encoding="utf-8")
    resource_link = tmp_path / "skill" / "notes.txt"
    resource_link.parent.mkdir()
    resource_link.symlink_to(private_file)

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
            SelectedSkillResource(skill_id="skill", resource_id="notes.txt"),
        )

    assert exc_info.value.category == "invalid_resource_path"


def test_load_resource_translates_read_error(tmp_path: Path, monkeypatch) -> None:
    resource_file = _write_resource(tmp_path, "read-error", "notes.txt", "read me")

    def raise_os_error(self: Path) -> bytes:
        assert self == resource_file
        msg = "synthetic read error"
        raise OSError(msg)

    monkeypatch.setattr(Path, "read_bytes", raise_os_error)

    with pytest.raises(SkillContextLoadError) as exc_info:
        SkillResourceFileContextLoader(skill_roots=(tmp_path,)).load(
            SelectedSkillResource(skill_id="read-error", resource_id="notes.txt"),
        )

    assert exc_info.value.category == "invalid_resource_file"


def _write_resource(root: Path, skill_id: str, resource_id: str, text: str) -> Path:
    resource_file = root / skill_id / resource_id
    resource_file.parent.mkdir(parents=True, exist_ok=True)
    resource_file.write_text(text, encoding="utf-8")
    return resource_file
