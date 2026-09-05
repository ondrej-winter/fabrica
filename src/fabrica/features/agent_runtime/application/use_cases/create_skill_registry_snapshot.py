"""Use case for constructing a run-scoped Agent Skill registry snapshot."""

from collections.abc import Callable
from uuid import uuid4

from fabrica.features.agent_runtime.application.dtos import (
    MAX_ENABLED_SKILLS,
    RegisteredSkill,
    SkillRegistrySnapshot,
)
from fabrica.features.agent_runtime.application.ports import SkillRegistryProvider, SkillRegistryProviderError


class CreateSkillRegistrySnapshot:
    """Discover healthy providers and capture their enabled skill metadata for one run."""

    def __init__(
        self,
        providers: tuple[SkillRegistryProvider, ...],
        *,
        snapshot_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._providers = providers
        self._snapshot_id_factory = snapshot_id_factory or _new_snapshot_id

    def create(self) -> SkillRegistrySnapshot:
        """Return an immutable snapshot while isolating individual provider failures."""
        registered_skills: list[RegisteredSkill] = []
        sources: set[str] = set()
        for provider in self._providers:
            if provider.source.value in sources:
                msg = "only one provider is permitted for each Version 1 skill source"
                raise ValueError(msg)
            sources.add(provider.source.value)
            try:
                definitions = provider.discover()
            except SkillRegistryProviderError:
                continue
            registered_skills.extend(
                RegisteredSkill(
                    skill_id=f"{provider.source.value}:{definition.name}",
                    source=provider.source,
                    definition=definition,
                )
                for definition in definitions
                if not definition.disabled
            )

        if len(registered_skills) > MAX_ENABLED_SKILLS:
            msg = "discovered enabled skill count exceeds the configured bound"
            raise ValueError(msg)
        return SkillRegistrySnapshot.create(snapshot_id=self._snapshot_id_factory(), skills=tuple(registered_skills))


def _new_snapshot_id() -> str:
    return f"skill-registry:{uuid4()}"
