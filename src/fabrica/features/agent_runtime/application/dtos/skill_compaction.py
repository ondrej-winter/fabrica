"""Application DTOs for preserving active skills across context compaction."""

from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos.skill_activation import ActiveSkill


@dataclass(frozen=True, slots=True)
class ActiveSkillCompactionState:
    """Ordered active-skill state retained by an owning runtime run."""

    run_id: str
    registry_snapshot_id: str
    skills: tuple[ActiveSkill, ...]

    def __post_init__(self) -> None:
        if not self.run_id:
            msg = "compacted active skill run ID must not be empty"
            raise ValueError(msg)
        if not self.registry_snapshot_id:
            msg = "compacted active skill registry snapshot ID must not be empty"
            raise ValueError(msg)
        object.__setattr__(self, "skills", tuple(self.skills))
