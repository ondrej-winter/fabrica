"""Use case for converting selected Agent Skills into runtime context."""

from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillContext,
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    SelectedSkill,
    SkillContextBounds,
)
from fabrica.features.agent_runtime.application.ports import SkillContextLoader


class LoadSkillContext:
    """Load selected skill markdown and shape it into runtime context blocks."""

    def __init__(self, loader: SkillContextLoader, bounds: SkillContextBounds | None = None) -> None:
        self._loader = loader
        self._bounds = bounds or SkillContextBounds()

    def load(self, selections: tuple[SelectedSkill, ...]) -> tuple[LocalAgentContextBlock, ...]:
        """Load selected skills and return bounded runtime context blocks."""
        if len(selections) > self._bounds.max_selected_skills:
            msg = "selected skill count exceeds the configured bound"
            raise ValueError(msg)

        loaded_skills = tuple(self._loader.load(selection) for selection in selections)
        self._validate_loaded_skills(loaded_skills)
        return tuple(self._to_context_block(skill) for skill in loaded_skills)

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

    def _validate_loaded_skills(self, loaded_skills: tuple[LoadedSkillContext, ...]) -> None:
        total_chars = 0
        for skill in loaded_skills:
            if len(skill.skill_id) > self._bounds.max_label_chars:
                msg = "loaded skill identifier exceeds the configured label bound"
                raise ValueError(msg)
            if len(skill.display_label) > self._bounds.max_label_chars:
                msg = "loaded skill label exceeds the configured label bound"
                raise ValueError(msg)
            if len(skill.markdown) > self._bounds.max_chars_per_skill:
                msg = "loaded skill markdown exceeds the configured per-skill bound"
                raise ValueError(msg)
            total_chars += len(skill.markdown)

        if total_chars > self._bounds.max_total_chars:
            msg = "loaded skill markdown exceeds the configured total bound"
            raise ValueError(msg)

    @staticmethod
    def _to_context_block(skill: LoadedSkillContext) -> LocalAgentContextBlock:
        return LocalAgentContextBlock(
            text=skill.markdown,
            label=f"Agent Skill: {skill.display_label}",
            metadata={
                "source": "agent_skill",
                "skill_id": skill.skill_id,
                **skill.metadata,
            },
        )
