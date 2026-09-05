"""Composition helpers for Version 1 Agent Skill registry snapshots."""

from pathlib import Path

from fabrica.features.agent_runtime.adapters.outbound.skill_directory_provider import (
    GlobalSkillDirectoryProvider,
    WorkspaceSkillDirectoryProvider,
)
from fabrica.features.agent_runtime.application.use_cases import CreateSkillRegistrySnapshot


def create_skill_registry_snapshot_builder(
    *,
    global_skill_root: Path | None = None,
    workspace_skill_root: Path | None = None,
) -> CreateSkillRegistrySnapshot:
    """Create a snapshot builder for configured global and workspace skill roots."""
    providers = ()
    if global_skill_root is not None:
        providers += (GlobalSkillDirectoryProvider(root=global_skill_root),)
    if workspace_skill_root is not None:
        providers += (WorkspaceSkillDirectoryProvider(root=workspace_skill_root),)
    return CreateSkillRegistrySnapshot(providers=providers)
