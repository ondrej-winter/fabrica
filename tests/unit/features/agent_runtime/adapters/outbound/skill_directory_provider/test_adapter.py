"""Tests for filesystem-backed Version 1 Agent Skill registry providers."""

from pathlib import Path

from fabrica.features.agent_runtime.adapters.outbound.skill_directory_provider import (
    GlobalSkillDirectoryProvider,
    WorkspaceSkillDirectoryProvider,
)
from fabrica.features.agent_runtime.application.dtos import SkillSource


def test_providers_discover_only_valid_direct_child_skills_in_deterministic_order(tmp_path: Path) -> None:
    _write_skill(tmp_path, "zebra", "Zebra skill.")
    _write_skill(tmp_path, "alpha", "Alpha skill.")
    _write_skill(tmp_path, "disabled", "Disabled skill.", disabled=True)
    _write_invalid_skill(tmp_path, "invalid")
    _write_skill(tmp_path / "nested", "ignored", "Nested skill.")

    global_definitions = GlobalSkillDirectoryProvider(root=tmp_path).discover()
    workspace_definitions = WorkspaceSkillDirectoryProvider(root=tmp_path).discover()

    assert [definition.name for definition in global_definitions] == ["alpha", "disabled", "zebra"]
    assert [definition.name for definition in workspace_definitions] == ["alpha", "disabled", "zebra"]
    assert GlobalSkillDirectoryProvider(root=tmp_path).source is SkillSource.GLOBAL
    assert WorkspaceSkillDirectoryProvider(root=tmp_path).source is SkillSource.WORKSPACE


def test_provider_returns_empty_when_root_is_unavailable(tmp_path: Path) -> None:
    assert GlobalSkillDirectoryProvider(root=tmp_path / "missing").discover() == ()


def _write_skill(root: Path, name: str, description: str, *, disabled: bool = False) -> None:
    skill_file = root / name / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {description}\ndisabled: {str(disabled).lower()}\n---\n\n# Instructions\n",
        encoding="utf-8",
    )


def _write_invalid_skill(root: Path, name: str) -> None:
    skill_file = root / name / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text("# Legacy\n", encoding="utf-8")
