"""Use case for converting selected Agent Skill resources into runtime context."""

from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillResourceContext,
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    SelectedSkillResource,
    SkillResourceContextBounds,
)
from fabrica.features.agent_runtime.application.ports import SkillResourceContextLoader


class LoadSkillResourceContext:
    """Load selected skill resources and shape them into runtime context blocks."""

    def __init__(self, loader: SkillResourceContextLoader, bounds: SkillResourceContextBounds | None = None) -> None:
        self._loader = loader
        self._bounds = bounds or SkillResourceContextBounds()

    def load(self, selections: tuple[SelectedSkillResource, ...]) -> tuple[LocalAgentContextBlock, ...]:
        """Load selected resources and return bounded runtime context blocks."""
        if len(selections) > self._bounds.max_selected_resources:
            msg = "selected skill resource count exceeds the configured bound"
            raise ValueError(msg)

        loaded_resources = tuple(self._loader.load(selection) for selection in selections)
        self._validate_loaded_resources(loaded_resources)
        return tuple(self._to_context_block(resource) for resource in loaded_resources)

    def augment_command(
        self,
        command: LocalAgentRunCommand,
        selections: tuple[SelectedSkillResource, ...],
    ) -> LocalAgentRunCommand:
        """Return a runtime command augmented with selected skill resource context."""
        resource_context = self.load(selections)
        return LocalAgentRunCommand(
            prompt=command.prompt,
            context=(*command.context, *resource_context),
            model_hint=command.model_hint,
        )

    def _validate_loaded_resources(self, loaded_resources: tuple[LoadedSkillResourceContext, ...]) -> None:
        total_chars = 0
        for resource in loaded_resources:
            if len(resource.skill_id) > self._bounds.max_label_chars:
                msg = "loaded skill identifier exceeds the configured label bound"
                raise ValueError(msg)
            if len(resource.resource_id) > self._bounds.max_label_chars:
                msg = "loaded skill resource identifier exceeds the configured label bound"
                raise ValueError(msg)
            if len(resource.display_label) > self._bounds.max_label_chars:
                msg = "loaded skill resource label exceeds the configured label bound"
                raise ValueError(msg)
            if len(resource.text) > self._bounds.max_chars_per_resource:
                msg = "loaded skill resource text exceeds the configured per-resource bound"
                raise ValueError(msg)
            total_chars += len(resource.text)

        if total_chars > self._bounds.max_total_chars:
            msg = "loaded skill resource text exceeds the configured total bound"
            raise ValueError(msg)

    @staticmethod
    def _to_context_block(resource: LoadedSkillResourceContext) -> LocalAgentContextBlock:
        return LocalAgentContextBlock(
            text=resource.text,
            label=f"Agent Skill Resource: {resource.display_label}",
            metadata={
                "source": "agent_skill_resource",
                "skill_id": resource.skill_id,
                "resource_id": resource.resource_id,
                "media_type": resource.media_type,
                **resource.metadata,
            },
        )
