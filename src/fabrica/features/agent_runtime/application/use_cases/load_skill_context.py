"""Use case for converting selected Agent Skills into runtime context."""

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    SelectedSkill,
    SkillContextBounds,
    SkillDefinition,
)
from fabrica.features.agent_runtime.application.ports import SkillDefinitionLoader


class LoadSkillContext:
    """Load canonical selected skill definitions into runtime context blocks."""

    def __init__(self, loader: SkillDefinitionLoader, bounds: SkillContextBounds | None = None) -> None:
        self._loader = loader
        self._bounds = bounds or SkillContextBounds()

    def load(self, selections: tuple[SelectedSkill, ...]) -> tuple[LocalAgentContextBlock, ...]:
        """Load selected skills and return bounded runtime context blocks."""
        if len(selections) > self._bounds.max_selected_skills:
            msg = "selected skill count exceeds the configured bound"
            raise ValueError(msg)

        definitions = tuple((selection, self._loader.load(selection)) for selection in selections)
        self._validate_definitions(definitions)
        return tuple(self._to_context_block(selection, definition) for selection, definition in definitions)

    def augment_command(
        self,
        command: LocalAgentRunCommand,
        selections: tuple[SelectedSkill, ...],
    ) -> LocalAgentRunCommand:
        """Return a runtime command augmented with selected skill context."""
        skill_context = self.load(selections)
        return LocalAgentRunCommand(
            prompt=command.prompt,
            context=(*command.context, *skill_context),
            model_hint=command.model_hint,
        )

    def _validate_definitions(self, definitions: tuple[tuple[SelectedSkill, SkillDefinition], ...]) -> None:
        total_chars = 0
        for selection, definition in definitions:
            if len(selection.skill_id) > self._bounds.max_label_chars:
                msg = "loaded skill identifier exceeds the configured label bound"
                raise ValueError(msg)
            display_label = selection.label or definition.name
            if len(display_label) > self._bounds.max_label_chars:
                msg = "loaded skill label exceeds the configured label bound"
                raise ValueError(msg)
            if len(definition.instructions) > self._bounds.max_chars_per_skill:
                msg = "loaded skill markdown exceeds the configured per-skill bound"
                raise ValueError(msg)
            total_chars += len(definition.instructions)

        if total_chars > self._bounds.max_total_chars:
            msg = "loaded skill markdown exceeds the configured total bound"
            raise ValueError(msg)

    @staticmethod
    def _to_context_block(selection: SelectedSkill, definition: SkillDefinition) -> LocalAgentContextBlock:
        return LocalAgentContextBlock(
            text=definition.instructions,
            label=f"Agent Skill: {selection.label or definition.name}",
            metadata={
                "source": "agent_skill",
                "skill_id": selection.skill_id,
                "name": definition.name,
                "description": definition.description,
                "revision": definition.revision,
            },
        )
