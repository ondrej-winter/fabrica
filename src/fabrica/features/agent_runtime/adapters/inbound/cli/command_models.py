"""Parsed command models for agent-runtime CLI commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from fabrica.features.agent_runtime.application.dtos import SkillScriptType


@dataclass(frozen=True, slots=True)
class CliSelectedResource:
    """Adapter-local reference to one selected skill resource argument."""

    skill_id: str
    resource_id: str


@dataclass(frozen=True, slots=True)
class CliRunCommand:
    """Parsed CLI arguments for one local runtime prompt run."""

    prompt: str
    model_hint: str | None = None
    skill_ids: tuple[str, ...] = field(default_factory=tuple)
    resources: tuple[CliSelectedResource, ...] = field(default_factory=tuple)
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_ids", tuple(self.skill_ids))
        object.__setattr__(self, "resources", tuple(self.resources))
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


@dataclass(frozen=True, slots=True)
class CliScriptPolicyCommand:
    """Parsed CLI arguments for selected skill script policy evaluation."""

    skill_id: str
    script_id: str
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


@dataclass(frozen=True, slots=True)
class CliScriptExecuteCommand:
    """Parsed CLI arguments for metadata-approved selected script execution."""

    skill_id: str
    script_id: str
    approval_script_type: SkillScriptType
    approval_suffix: str
    approval_byte_size: int
    approval_content_digest: str
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))
