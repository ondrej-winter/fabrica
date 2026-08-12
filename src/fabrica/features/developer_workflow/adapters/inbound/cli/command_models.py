"""Parsed command models for developer-workflow CLI commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fabrica.features.developer_workflow.application.dtos import DEFAULT_COMMIT_MESSAGE_SKILL_ID

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class CliDeveloperWorkflowCompositionOptions:
    """Adapter-local options consumed by bootstrap developer-workflow composition."""

    model: str | None = None
    reasoning_effort: str | None = None
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


@dataclass(frozen=True, slots=True)
class CliCommitMessageCommand:
    """Parsed CLI use-case input for selected-skill commit-message generation."""

    skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    composition_options: CliDeveloperWorkflowCompositionOptions = field(
        default_factory=CliDeveloperWorkflowCompositionOptions,
    )


@dataclass(frozen=True, slots=True)
class CliCommitCommand:
    """Parsed CLI use-case input for interactive confirmed git commit creation."""

    skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    composition_options: CliDeveloperWorkflowCompositionOptions = field(
        default_factory=CliDeveloperWorkflowCompositionOptions,
    )
