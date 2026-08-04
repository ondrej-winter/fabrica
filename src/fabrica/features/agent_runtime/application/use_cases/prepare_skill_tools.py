"""Use case for normalizing selected Agent Skill tool exposure."""

from fabrica.features.agent_runtime.application.dtos import (
    RuntimeObservation,
    SelectedSkillToolDeclaration,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    SkillToolPreparationResult,
)
from fabrica.features.agent_runtime.application.ports import SkillToolPreparationError, SkillToolPreparer


class PrepareSkillTools:
    """Prepare model-callable tool definitions for explicitly selected skills."""

    def __init__(self, preparer: SkillToolPreparer) -> None:
        self._preparer = preparer

    def prepare(self, command: SkillToolPreparationCommand) -> SkillToolPreparationResult:
        """Return normalized fail-closed declarations for selected skill tools."""
        try:
            prepared = self._preparer.prepare(command)
        except SkillToolPreparationError as err:
            return SkillToolPreparationResult(
                observations=(
                    RuntimeObservation(
                        message="skill tool preparation adapter failed",
                        metadata={"category": err.category, **err.metadata},
                    ),
                ),
            )
        return self._normalize(command, prepared)

    @staticmethod
    def _normalize(
        command: SkillToolPreparationCommand,
        prepared: SkillToolPreparationResult,
    ) -> SkillToolPreparationResult:
        selected_skill_ids = command.selected_skill_ids
        seen_tool_names: set[str] = set()
        declarations: list[SelectedSkillToolDeclaration] = []
        observations = list(prepared.observations)

        for declaration in prepared.declarations:
            normalized = declaration
            if declaration.skill_id not in selected_skill_ids:
                normalized = declaration.with_status(
                    SkillToolExposureStatus.UNKNOWN_SELECTION,
                    reason="skill was not explicitly selected",
                    metadata={"skill_id": declaration.skill_id},
                )
            elif declaration.exposes_model_tool:
                assert declaration.tool is not None
                if declaration.tool.name in seen_tool_names:
                    normalized = declaration.with_status(
                        SkillToolExposureStatus.DUPLICATE,
                        reason="tool name was already registered for this preparation request",
                        metadata={"tool_name": declaration.tool.name},
                    )
                else:
                    seen_tool_names.add(declaration.tool.name)

            if normalized.status is SkillToolExposureStatus.SCRIPT_DEFERRED:
                observations.append(
                    RuntimeObservation(
                        message="selected skill script was not exposed as a model-callable tool",
                        metadata={"skill_id": normalized.skill_id, "status": normalized.status.value},
                    ),
                )
            declarations.append(normalized)

        return SkillToolPreparationResult(declarations=tuple(declarations), observations=tuple(observations))
