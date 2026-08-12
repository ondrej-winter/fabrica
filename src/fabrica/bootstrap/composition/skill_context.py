"""Composition helpers for selected Agent Skill context."""

from dataclasses import dataclass, field
from pathlib import Path

from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import (
    SkillMarkdownFileContextLoader,
    SkillResourceFileContextLoader,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SelectedSkill,
    SelectedSkillResource,
    SkillContextBounds,
    SkillResourceContextBounds,
)
from fabrica.features.agent_runtime.application.use_cases import LoadSkillContext, LoadSkillResourceContext


@dataclass(frozen=True, slots=True)
class SkillContextAugmentationOptions:
    """Composition options for selected skill markdown and resource context.

    Selected files are loaded lazily when a command is augmented or when a
    composed model-driven runtime is run. ``verbose_diagnostics`` may include
    additional non-secret troubleshooting metadata in result observations.
    """

    skill_selections: tuple[SelectedSkill, ...] = field(default_factory=tuple)
    resource_selections: tuple[SelectedSkillResource, ...] = field(default_factory=tuple)
    skill_roots: tuple[Path, ...] | None = None
    skill_bounds: SkillContextBounds | None = None
    resource_bounds: SkillResourceContextBounds | None = None
    verbose_diagnostics: bool = False


def create_skill_context_loader(
    *,
    skill_roots: tuple[Path, ...] | None = None,
    bounds: SkillContextBounds | None = None,
    verbose_diagnostics: bool = False,
) -> LoadSkillContext:
    """Create a use case for loading selected local Agent Skills as runtime context.

    The helper wires filesystem access at the composition root. It only constructs
    dependencies; selected ``SKILL.md`` files are read when the returned use case
    is called.
    """
    return LoadSkillContext(
        loader=SkillMarkdownFileContextLoader(
            skill_roots=skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
        bounds=bounds,
    )


def create_skill_augmented_local_agent_command(
    command: LocalAgentRunCommand,
    selections: tuple[SelectedSkill, ...],
    *,
    skill_roots: tuple[Path, ...] | None = None,
    bounds: SkillContextBounds | None = None,
    verbose_diagnostics: bool = False,
) -> LocalAgentRunCommand:
    """Return a local runtime command augmented with selected Agent Skill context.

    This helper loads explicitly selected local ``SKILL.md`` markdown only. It
    does not create a Codex runtime, read Codex credentials, call a backend, or
    execute skill scripts/resources.
    """
    skill_context_loader = create_skill_context_loader(
        skill_roots=skill_roots,
        bounds=bounds,
        verbose_diagnostics=verbose_diagnostics,
    )
    return skill_context_loader.augment_command(command, selections)


def create_skill_resource_context_loader(
    *,
    skill_roots: tuple[Path, ...] | None = None,
    bounds: SkillResourceContextBounds | None = None,
    verbose_diagnostics: bool = False,
) -> LoadSkillResourceContext:
    """Create a use case for loading selected Agent Skill resources as context."""
    return LoadSkillResourceContext(
        loader=SkillResourceFileContextLoader(
            skill_roots=skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
        bounds=bounds,
    )


def create_skill_resource_augmented_local_agent_command(
    command: LocalAgentRunCommand,
    selections: tuple[SelectedSkillResource, ...],
    *,
    skill_roots: tuple[Path, ...] | None = None,
    bounds: SkillResourceContextBounds | None = None,
    verbose_diagnostics: bool = False,
) -> LocalAgentRunCommand:
    """Return a local runtime command augmented with selected skill resources."""
    resource_context_loader = create_skill_resource_context_loader(
        skill_roots=skill_roots,
        bounds=bounds,
        verbose_diagnostics=verbose_diagnostics,
    )
    return resource_context_loader.augment_command(command, selections)


def create_skill_context_augmented_local_agent_command(
    command: LocalAgentRunCommand,
    options: SkillContextAugmentationOptions,
) -> LocalAgentRunCommand:
    """Return a command augmented with selected skill markdown and resources."""
    augmented = command
    if options.skill_selections:
        augmented = create_skill_augmented_local_agent_command(
            augmented,
            options.skill_selections,
            skill_roots=options.skill_roots,
            bounds=options.skill_bounds,
            verbose_diagnostics=options.verbose_diagnostics,
        )
    if options.resource_selections:
        augmented = create_skill_resource_augmented_local_agent_command(
            augmented,
            options.resource_selections,
            skill_roots=options.skill_roots,
            bounds=options.resource_bounds,
            verbose_diagnostics=options.verbose_diagnostics,
        )
    return augmented
