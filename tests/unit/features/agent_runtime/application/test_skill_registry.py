"""Tests for immutable Version 1 Agent Skill registry snapshots."""

from dataclasses import dataclass

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    MAX_ADVERTISED_CATALOG_CHARS,
    RegisteredSkill,
    SkillDefinition,
    SkillRegistrySnapshot,
    SkillResolutionStatus,
    SkillSource,
)
from fabrica.features.agent_runtime.application.ports import SkillRegistryProviderError
from fabrica.features.agent_runtime.application.use_cases import CreateSkillRegistrySnapshot


def test_snapshot_resolves_canonical_and_unique_bare_names_and_reports_ambiguity() -> None:
    snapshot = SkillRegistrySnapshot.create(
        snapshot_id="snapshot-1",
        skills=(
            _registered_skill(source=SkillSource.GLOBAL, name="commit"),
            _registered_skill(source=SkillSource.GLOBAL, name="review-pr"),
            _registered_skill(source=SkillSource.WORKSPACE, name="review-pr"),
        ),
    )

    canonical = snapshot.resolve(" /GLOBAL:COMMIT ")
    unique_bare_name = snapshot.resolve("commit")
    ambiguous = snapshot.resolve("/review-pr")
    missing = snapshot.resolve("missing")

    assert canonical.status is SkillResolutionStatus.FOUND
    assert canonical.skill is not None
    assert canonical.skill.skill_id == "global:commit"
    assert unique_bare_name.status is SkillResolutionStatus.FOUND
    assert unique_bare_name.skill is not None
    assert unique_bare_name.skill.skill_id == "global:commit"
    assert ambiguous.status is SkillResolutionStatus.AMBIGUOUS
    assert ambiguous.candidates == ("global:review-pr", "workspace:review-pr")
    assert missing.status is SkillResolutionStatus.MISSING


def test_snapshot_catalog_is_sorted_complete_entry_bounded_and_marks_omissions() -> None:
    snapshot = SkillRegistrySnapshot.create(
        snapshot_id="snapshot-1",
        skills=tuple(
            _registered_skill(source=SkillSource.GLOBAL, name=f"skill-{index}", description="x" * 512)
            for index in range(8)
        ),
    )

    catalog = snapshot.catalog_description()

    assert len(catalog) <= MAX_ADVERTISED_CATALOG_CHARS
    assert "global:skill-0" in catalog
    assert "global:skill-1" not in catalog
    assert "Additional configured skills are not shown" in catalog


def test_snapshot_builder_is_stable_when_provider_data_changes_and_isolates_failure() -> None:
    healthy_provider = FakeProvider(
        source=SkillSource.GLOBAL,
        definitions=[_definition("commit")],
    )
    failing_provider = FailingProvider(source=SkillSource.WORKSPACE)
    builder = CreateSkillRegistrySnapshot(
        providers=(healthy_provider, failing_provider),
        snapshot_id_factory=lambda: "snapshot-1",
    )

    snapshot = builder.create()
    healthy_provider.definitions.append(_definition("review-pr"))

    assert tuple(skill.skill_id for skill in snapshot.skills) == ("global:commit",)
    assert snapshot.resolve("review-pr").status is SkillResolutionStatus.MISSING
    assert tuple(skill.skill_id for skill in builder.create().skills) == ("global:commit", "global:review-pr")


def test_snapshot_builder_omits_disabled_definitions_and_rejects_duplicate_source_providers() -> None:
    disabled_provider = FakeProvider(source=SkillSource.GLOBAL, definitions=[_definition("disabled", disabled=True)])
    builder = CreateSkillRegistrySnapshot(providers=(disabled_provider,), snapshot_id_factory=lambda: "snapshot-1")

    assert builder.create().skills == ()

    with pytest.raises(ValueError, match="one provider"):
        CreateSkillRegistrySnapshot(
            providers=(disabled_provider, FakeProvider(source=SkillSource.GLOBAL, definitions=[])),
        ).create()


@dataclass
class FakeProvider:
    source: SkillSource
    definitions: list[SkillDefinition]

    def discover(self) -> tuple[SkillDefinition, ...]:
        return tuple(self.definitions)


@dataclass
class FailingProvider:
    source: SkillSource

    def discover(self) -> tuple[SkillDefinition, ...]:
        msg = "provider unavailable"
        raise SkillRegistryProviderError(msg)


def _registered_skill(*, source: SkillSource, name: str, description: str = "Description.") -> RegisteredSkill:
    definition = _definition(name, description=description)
    return RegisteredSkill(skill_id=f"{source.value}:{name}", source=source, definition=definition)


def _definition(name: str, *, description: str = "Description.", disabled: bool = False) -> SkillDefinition:
    return SkillDefinition.from_skill_file_bytes(
        name=name,
        description=description,
        instructions="# Instructions\n",
        skill_file_bytes=f"{name}:{description}".encode(),
        disabled=disabled,
    )
