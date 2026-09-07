"""Tests for canonical YAML-frontmatter Agent Skill definition loading."""

from hashlib import sha256
from pathlib import Path

import pytest

from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import SkillMarkdownFileDefinitionLoader
from fabrica.features.agent_runtime.application.dtos import SelectedSkill
from fabrica.features.agent_runtime.application.ports import SkillDefinitionLoadError


def test_load_returns_canonical_definition_and_exact_source_revision(tmp_path: Path) -> None:
    source = (
        "---\nname: review-pr\ndescription: Review pull requests.\ndisabled: false\n"
        "metadata:\n  version: 1\n  dependencies:\n    skills:\n"
        "      - name: write-tests\n        required: false\n---\n\n"
        "# Review\n\nInspect changes.\n"
    )
    _write_skill(tmp_path, "review-pr", source)

    definition = SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="review-pr"))

    assert definition.name == "review-pr"
    assert definition.description == "Review pull requests."
    assert definition.instructions == "# Review\n\nInspect changes.\n"
    assert definition.disabled is False
    assert definition.metadata == {
        "version": 1,
        "dependencies": {"skills": ({"name": "write-tests", "required": False},)},
    }
    assert definition.revision == f"sha256:{sha256(source.encode()).hexdigest()}"


@pytest.mark.parametrize(
    ("skill_id", "source", "category"),
    [
        ("review-pr", "# Legacy\n\nHeading-only skill.", "invalid_frontmatter"),
        ("review-pr", "\ufeff---\nname: review-pr\ndescription: Description.\n---\n\n# Body", "utf8_bom"),
        ("review-pr", "---\nname: review-pr\ndescription: [\n---\n\n# Body", "invalid_frontmatter"),
        ("review-pr", "---\nname: review-pr\n---\n\n# Body", "invalid_definition"),
        ("review-pr", "---\nname: Review-PR\ndescription: Description.\n---\n\n# Body", "invalid_definition"),
        ("other", "---\nname: review-pr\ndescription: Description.\n---\n\n# Body", "invalid_definition"),
        ("review-pr", "---\nname: review-pr\ndescription: Description.\n---\n\n  \n", "invalid_definition"),
        (
            "review-pr",
            "---\nname: review-pr\ndescription: Description.\ndisabled: 'no'\n---\n\n# Body",
            "invalid_definition",
        ),
        (
            "review-pr",
            "---\nname: review-pr\ndescription: Description.\nextra: value\n---\n\n# Body",
            "invalid_definition",
        ),
        (
            "review-pr",
            "---\nname: review-pr\ndescription: Description.\nmetadata: invalid\n---\n\n# Body",
            "invalid_definition",
        ),
    ],
)
def test_load_rejects_invalid_canonical_skill_files(
    tmp_path: Path,
    skill_id: str,
    source: str,
    category: str,
) -> None:
    _write_skill(tmp_path, skill_id, source)

    with pytest.raises(SkillDefinitionLoadError) as exc_info:
        SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id=skill_id))

    assert exc_info.value.category == category
    assert str(tmp_path) not in str(exc_info.value)
    assert "path" not in exc_info.value.metadata


def test_load_rejects_invalid_utf8_and_oversized_instruction_content(tmp_path: Path) -> None:
    invalid_file = tmp_path / "invalid-utf8" / "SKILL.md"
    invalid_file.parent.mkdir(parents=True)
    invalid_file.write_bytes(b"\xff\xfe")

    with pytest.raises(SkillDefinitionLoadError, match="UTF-8") as decode_error:
        SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="invalid-utf8"))

    assert decode_error.value.category == "decode_error"

    _write_skill(
        tmp_path,
        "oversized",
        "---\nname: oversized\ndescription: Oversized instructions.\n---\n\n" + "x" * 20_001,
    )
    with pytest.raises(SkillDefinitionLoadError) as size_error:
        SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="oversized"))

    assert size_error.value.category == "skill_too_large"


def test_definition_loader_rejects_symlinked_skill_directory_outside_root(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    _write_skill(private_root, "escaped", "---\nname: escaped\ndescription: Private.\n---\n\n# Private\n")
    skill_root = tmp_path / "skills"
    linked_private_root = skill_root / "linked-private"
    linked_private_root.parent.mkdir(parents=True)
    linked_private_root.symlink_to(private_root, target_is_directory=True)

    with pytest.raises(SkillDefinitionLoadError) as exc_info:
        SkillMarkdownFileDefinitionLoader(skill_roots=(skill_root,)).load(
            SelectedSkill(skill_id="linked-private/escaped"),
        )

    assert exc_info.value.category == "invalid_skill_path"


def test_definition_loader_rejects_directory_read_errors_and_unclosed_frontmatter(tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "directory-shape" / "SKILL.md"
    directory.mkdir(parents=True)

    with pytest.raises(SkillDefinitionLoadError) as directory_error:
        SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="directory-shape"))

    assert directory_error.value.category == "invalid_skill_file"

    skill_file = _write_skill(
        tmp_path, "read-error", "---\nname: read-error\ndescription: Read error.\n---\n\n# Body\n"
    )

    def raise_os_error(self: Path) -> bytes:
        assert self == skill_file
        msg = "synthetic read error"
        raise OSError(msg)

    monkeypatch.setattr(Path, "read_bytes", raise_os_error)

    with pytest.raises(SkillDefinitionLoadError) as read_error:
        SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,)).load(SelectedSkill(skill_id="read-error"))

    assert read_error.value.category == "invalid_skill_file"


def test_definition_loader_reports_unclosed_frontmatter_and_verbose_path(tmp_path: Path) -> None:
    _write_skill(tmp_path, "unclosed", "---\nname: unclosed\ndescription: Missing closing delimiter.\n# Body\n")

    with pytest.raises(SkillDefinitionLoadError) as exc_info:
        SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,), verbose_diagnostics=True).load(
            SelectedSkill(skill_id="unclosed"),
        )

    assert exc_info.value.category == "invalid_frontmatter"
    assert exc_info.value.metadata["diagnostic_mode"] == "verbose"
    assert isinstance(exc_info.value.metadata["path"], str)
    assert exc_info.value.metadata["path"].endswith("unclosed/SKILL.md")


def _write_skill(root: Path, skill_id: str, source: str) -> Path:
    skill_file = root / skill_id / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(source, encoding="utf-8")
    return skill_file
