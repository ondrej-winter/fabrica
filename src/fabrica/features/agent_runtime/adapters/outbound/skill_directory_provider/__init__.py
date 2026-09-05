"""Filesystem-backed Version 1 Agent Skill registry provider adapters."""

from fabrica.features.agent_runtime.adapters.outbound.skill_directory_provider.adapter import (
    GlobalSkillDirectoryProvider,
    WorkspaceSkillDirectoryProvider,
)

__all__ = ["GlobalSkillDirectoryProvider", "WorkspaceSkillDirectoryProvider"]
