"""Tests for exact-binding trust and safe reread revision adapters."""

from pathlib import Path

import pytest

from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import SkillMarkdownFileDefinitionLoader
from fabrica.features.agent_runtime.adapters.outbound.skill_trust import (
    MetadataBoundSkillTrustLookup,
    SourceMappedSkillRevisionDefinitionLoader,
)
from fabrica.features.agent_runtime.application.dtos import (
    RegisteredSkill,
    SkillDefinition,
    SkillSource,
    SkillTrustBinding,
    SkillTrustDecisionStatus,
)
from fabrica.features.agent_runtime.application.ports import SkillRevisionLoadError


def test_metadata_bound_lookup_requires_exact_workspace_run_skill_source_and_revision() -> None:
    binding = _binding()
    lookup = MetadataBoundSkillTrustLookup(expected_binding=binding)

    assert lookup.get_decision(binding).status is SkillTrustDecisionStatus.APPROVED_FOR_RUN

    for changed_binding in (
        _binding(workspace_identity="workspace-2"),
        _binding(run_id="run-2"),
        _binding(skill_id="workspace:release"),
        _binding(revision="sha256:" + "2" * 64),
    ):
        assert lookup.get_decision(changed_binding).status is SkillTrustDecisionStatus.DENIED


def test_metadata_bound_lookup_rejects_denied_configured_status() -> None:
    with pytest.raises(ValueError, match="non-denied"):
        MetadataBoundSkillTrustLookup(expected_binding=_binding(), approved_status=SkillTrustDecisionStatus.DENIED)


def test_source_mapped_loader_rereads_canonical_definition_without_exposing_paths(tmp_path: Path) -> None:
    source = "---\nname: review-pr\ndescription: Review pull requests.\n---\n\n# Instructions\n"
    skill_file = tmp_path / "review-pr" / "SKILL.md"
    skill_file.parent.mkdir()
    skill_file.write_text(source, encoding="utf-8")
    registered = RegisteredSkill(
        skill_id="workspace:review-pr",
        source=SkillSource.WORKSPACE,
        definition=SkillDefinition.from_skill_file_bytes(
            name="review-pr",
            description="Review pull requests.",
            instructions="# Instructions\n",
            skill_file_bytes=source.encode(),
        ),
    )
    loader = SourceMappedSkillRevisionDefinitionLoader(
        loaders_by_source={SkillSource.WORKSPACE: SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,))},
    )

    assert loader.load_registered(registered).revision == registered.revision

    skill_file.write_text(source.replace("# Instructions", "# Changed"), encoding="utf-8")

    assert loader.load_registered(registered).revision != registered.revision


def test_source_mapped_loader_translates_missing_source_or_definition_errors(tmp_path: Path) -> None:
    registered = _registered_skill()

    with pytest.raises(SkillRevisionLoadError, match="source definition loader"):
        SourceMappedSkillRevisionDefinitionLoader(loaders_by_source={}).load_registered(registered)

    loader = SourceMappedSkillRevisionDefinitionLoader(
        loaders_by_source={SkillSource.WORKSPACE: SkillMarkdownFileDefinitionLoader(skill_roots=(tmp_path,))},
    )

    with pytest.raises(SkillRevisionLoadError, match="could not be reread"):
        loader.load_registered(registered)


def _binding(
    *,
    workspace_identity: str = "workspace-1",
    run_id: str = "run-1",
    skill_id: str = "workspace:review-pr",
    revision: str = "sha256:" + "1" * 64,
) -> SkillTrustBinding:
    return SkillTrustBinding(
        workspace_identity=workspace_identity,
        run_id=run_id,
        skill_id=skill_id,
        source=SkillSource.WORKSPACE,
        revision=revision,
    )


def _registered_skill() -> RegisteredSkill:
    definition = SkillDefinition.from_skill_file_bytes(
        name="review-pr",
        description="Review pull requests.",
        instructions="# Instructions\n",
        skill_file_bytes=b"source",
    )
    return RegisteredSkill(skill_id="workspace:review-pr", source=SkillSource.WORKSPACE, definition=definition)
