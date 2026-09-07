"""Rehydrate required active-skill instructions into a compacted run command."""

from dataclasses import dataclass
from enum import StrEnum

from fabrica.features.agent_runtime.application.dtos import (
    ActiveSkill,
    ActiveSkillCompactionState,
    ActiveSkillSet,
    LocalAgentContextBlock,
    LocalAgentRunCommand,
)


class ActiveSkillContextRehydrationStatus(StrEnum):
    """Outcomes for fail-closed active-skill context reconstruction."""

    REHYDRATED = "rehydrated"
    MALFORMED_STATE = "malformed_state"
    ACTIVE_SKILL_CONTEXT_OVERFLOW = "active_skill_context_overflow"


@dataclass(frozen=True, slots=True)
class ActiveSkillContextRehydrationResult:
    """Rehydrated command or host-visible reason it cannot be resumed safely."""

    status: ActiveSkillContextRehydrationStatus
    command: LocalAgentRunCommand | None = None


class RehydrateActiveSkillContext:
    """Persist and rebuild ordered active skill context for one runtime run."""

    def __init__(self, *, max_total_context_chars: int) -> None:
        if max_total_context_chars < 1:
            msg = "active skill context budget must be at least 1"
            raise ValueError(msg)
        self._max_total_context_chars = max_total_context_chars

    @staticmethod
    def compact(active_skills: ActiveSkillSet) -> ActiveSkillCompactionState:
        """Snapshot the exact ordered active state for later run resumption."""
        return ActiveSkillCompactionState(
            run_id=active_skills.run_id,
            registry_snapshot_id=active_skills.registry_snapshot_id,
            skills=active_skills.skills,
        )

    def rehydrate(
        self,
        command: LocalAgentRunCommand,
        *,
        state: ActiveSkillCompactionState | None,
        run_id: str,
        registry_snapshot_id: str,
    ) -> ActiveSkillContextRehydrationResult:
        """Return a command with required skills before retrieved command context."""
        if not _is_valid_state(state, run_id=run_id, registry_snapshot_id=registry_snapshot_id):
            return ActiveSkillContextRehydrationResult(ActiveSkillContextRehydrationStatus.MALFORMED_STATE)
        if state is None:  # pragma: no cover - _is_valid_state returns false for None immediately above.
            return ActiveSkillContextRehydrationResult(ActiveSkillContextRehydrationStatus.MALFORMED_STATE)
        skill_context = tuple(_to_context_block(skill) for skill in state.skills)
        augmented = LocalAgentRunCommand(
            prompt=command.prompt,
            context=(*skill_context, *command.context),
            instructions=command.instructions,
            model_hint=command.model_hint,
        )
        if _context_size(augmented) > self._max_total_context_chars:
            return ActiveSkillContextRehydrationResult(
                ActiveSkillContextRehydrationStatus.ACTIVE_SKILL_CONTEXT_OVERFLOW,
            )
        return ActiveSkillContextRehydrationResult(ActiveSkillContextRehydrationStatus.REHYDRATED, command=augmented)


def _is_valid_state(
    state: ActiveSkillCompactionState | None,
    *,
    run_id: str,
    registry_snapshot_id: str,
) -> bool:
    if state is None or state.run_id != run_id or state.registry_snapshot_id != registry_snapshot_id:
        return False
    expected_order = tuple(range(len(state.skills)))
    return all(
        skill.activation_order == expected_order[index] and skill.registry_snapshot_id == registry_snapshot_id
        for index, skill in enumerate(state.skills)
    )


def _to_context_block(skill: ActiveSkill) -> LocalAgentContextBlock:
    return LocalAgentContextBlock(
        text=skill.instructions,
        label=f"Active Agent Skill: {skill.skill_id}",
        metadata={
            "source": "active_agent_skill",
            "skill_id": skill.skill_id,
            "revision": skill.instruction_revision,
            "activation_order": skill.activation_order,
            "registry_snapshot_id": skill.registry_snapshot_id,
        },
    )


def _context_size(command: LocalAgentRunCommand) -> int:
    return len(command.prompt) + sum(len(block.text) for block in command.context)
