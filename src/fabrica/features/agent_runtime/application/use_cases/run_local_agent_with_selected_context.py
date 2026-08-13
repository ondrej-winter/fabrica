"""Use case for running a local agent with explicitly selected skill context."""

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    SelectedSkill,
    SelectedSkillResource,
)
from fabrica.features.agent_runtime.application.ports import LocalAgentRuntime
from fabrica.features.agent_runtime.application.use_cases.load_skill_context import LoadSkillContext
from fabrica.features.agent_runtime.application.use_cases.load_skill_resource_context import LoadSkillResourceContext


class RunLocalAgentWithSelectedContext:
    """Augment a local agent command with selected context before running it."""

    def __init__(
        self,
        *,
        runtime: LocalAgentRuntime,
        skill_context_loader: LoadSkillContext | None = None,
        skill_resource_context_loader: LoadSkillResourceContext | None = None,
    ) -> None:
        self._runtime = runtime
        self._skill_context_loader = skill_context_loader
        self._skill_resource_context_loader = skill_resource_context_loader

    def run(
        self,
        command: LocalAgentRunCommand,
        *,
        skill_selections: tuple[SelectedSkill, ...] = (),
        resource_selections: tuple[SelectedSkillResource, ...] = (),
    ) -> LocalAgentRunResult:
        """Run a command after adding explicitly selected skill and resource context."""
        augmented = command
        if skill_selections:
            skill_context_loader = self._require_skill_context_loader()
            augmented = skill_context_loader.augment_command(augmented, skill_selections)
        if resource_selections:
            skill_resource_context_loader = self._require_skill_resource_context_loader()
            augmented = skill_resource_context_loader.augment_command(augmented, resource_selections)
        return self._runtime.run(augmented)

    def _require_skill_context_loader(self) -> LoadSkillContext:
        if self._skill_context_loader is None:
            msg = "selected skill context loader is not configured"
            raise RuntimeError(msg)
        return self._skill_context_loader

    def _require_skill_resource_context_loader(self) -> LoadSkillResourceContext:
        if self._skill_resource_context_loader is None:
            msg = "selected skill resource context loader is not configured"
            raise RuntimeError(msg)
        return self._skill_resource_context_loader
