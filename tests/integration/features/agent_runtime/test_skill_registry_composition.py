"""Integration coverage for global and workspace Agent Skill registry composition."""

from pathlib import Path

from fabrica.bootstrap.composition import create_skill_registry_snapshot_builder
from fabrica.features.agent_runtime.application.dtos import SkillResolutionStatus


def test_composition_builds_one_snapshot_from_global_and_workspace_skill_roots(tmp_path: Path) -> None:
    global_root = tmp_path / "global"
    workspace_root = tmp_path / "workspace"
    _write_skill(global_root, "commit", "Create focused conventional commits.")
    _write_skill(workspace_root, "review-pr", "Review pull requests.")
    _write_skill(workspace_root, "disabled", "Disabled skill.", disabled=True)

    snapshot = create_skill_registry_snapshot_builder(
        global_skill_root=global_root,
        workspace_skill_root=workspace_root,
    ).create()

    assert tuple(skill.skill_id for skill in snapshot.skills) == ("global:commit", "workspace:review-pr")
    assert snapshot.resolve("commit").status is SkillResolutionStatus.FOUND
    assert snapshot.resolve("review-pr").status is SkillResolutionStatus.FOUND
    assert snapshot.resolve("disabled").status is SkillResolutionStatus.MISSING


def _write_skill(root: Path, name: str, description: str, *, disabled: bool = False) -> None:
    skill_file = root / name / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {description}\ndisabled: {str(disabled).lower()}\n---\n\n# Instructions\n",
        encoding="utf-8",
    )
