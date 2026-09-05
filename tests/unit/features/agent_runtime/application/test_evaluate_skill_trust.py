"""Tests for revision-bound Version 1 Agent Skill trust evaluation."""

from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredSkill,
    SkillDefinition,
    SkillSource,
    SkillTrustBinding,
    SkillTrustDecision,
    SkillTrustDecisionStatus,
    SkillTrustEvaluationCommand,
    SkillTrustEvaluationStatus,
)
from fabrica.features.agent_runtime.application.ports import SkillRevisionLoadError
from fabrica.features.agent_runtime.application.use_cases import EvaluateSkillTrust


@dataclass
class FakeTrustLookup:
    decision: SkillTrustDecision
    bindings: list[SkillTrustBinding] = field(default_factory=list)

    def get_decision(self, binding: SkillTrustBinding) -> SkillTrustDecision:
        self.bindings.append(binding)
        return self.decision


@dataclass
class FakeRevisionLoader:
    definition: SkillDefinition | None
    calls: list[RegisteredSkill] = field(default_factory=list)

    def load_registered(self, skill: RegisteredSkill) -> SkillDefinition:
        self.calls.append(skill)
        if self.definition is None:
            msg = "unavailable"
            raise SkillRevisionLoadError(msg)
        return self.definition


def test_evaluate_approves_only_when_exact_binding_and_reread_revision_match() -> None:
    skill = _skill()
    command = _command(skill)
    lookup = FakeTrustLookup(_decision(command.binding, SkillTrustDecisionStatus.APPROVED_FOR_RUN))
    loader = FakeRevisionLoader(definition=skill.definition)

    result = EvaluateSkillTrust(lookup, loader).evaluate(command)

    assert result.status is SkillTrustEvaluationStatus.APPROVED
    assert result.definition == skill.definition
    assert lookup.bindings == [command.binding]
    assert loader.calls == [skill]


def test_evaluate_rejects_allowlist_before_trust_or_definition_loading() -> None:
    skill = _skill()
    command = _command(skill, allowed_skill_ids=frozenset({"global:commit"}))
    lookup = FakeTrustLookup(_decision(command.binding, SkillTrustDecisionStatus.TRUSTED))
    loader = FakeRevisionLoader(definition=skill.definition)

    result = EvaluateSkillTrust(lookup, loader).evaluate(command)

    assert result.status is SkillTrustEvaluationStatus.NOT_ALLOWED
    assert result.definition is None
    assert lookup.bindings == []
    assert loader.calls == []


def test_workspace_approval_cannot_be_reused_for_another_workspace_run_skill_or_revision() -> None:
    approved_command = _command(_skill())
    lookup = FakeTrustLookup(_decision(approved_command.binding, SkillTrustDecisionStatus.APPROVED_FOR_RUN))

    for command in (
        _command(_skill(), workspace_identity="workspace-other"),
        _command(_skill(), run_id="run-other"),
        _command(_skill(name="release")),
        _command(_skill(source_bytes=b"changed")),
    ):
        loader = FakeRevisionLoader(definition=command.skill.definition)

        result = EvaluateSkillTrust(lookup, loader).evaluate(command)

        assert result.status is SkillTrustEvaluationStatus.UNTRUSTED
        assert result.definition is None
        assert loader.calls == []


def test_evaluate_rejects_changed_or_disabled_reread_definition_without_disclosing_it() -> None:
    skill = _skill()
    command = _command(skill)
    lookup = FakeTrustLookup(_decision(command.binding, SkillTrustDecisionStatus.TRUSTED))

    for definition in (
        _definition("review-pr", source_bytes=b"changed"),
        _definition("review-pr", source_bytes=b"same", disabled=True),
    ):
        result = EvaluateSkillTrust(lookup, FakeRevisionLoader(definition=definition)).evaluate(command)

        assert result.status is SkillTrustEvaluationStatus.REVISION_MISMATCH
        assert result.definition is None


def test_evaluate_returns_unavailable_when_safe_reread_fails() -> None:
    skill = _skill()
    command = _command(skill)
    lookup = FakeTrustLookup(_decision(command.binding, SkillTrustDecisionStatus.TRUSTED))

    result = EvaluateSkillTrust(lookup, FakeRevisionLoader(definition=None)).evaluate(command)

    assert result.status is SkillTrustEvaluationStatus.DEFINITION_UNAVAILABLE
    assert result.definition is None


def _command(
    skill: RegisteredSkill,
    *,
    workspace_identity: str = "workspace-1",
    run_id: str = "run-1",
    allowed_skill_ids: frozenset[str] | None = None,
) -> SkillTrustEvaluationCommand:
    return SkillTrustEvaluationCommand(
        workspace_identity=workspace_identity,
        run_id=run_id,
        skill=skill,
        allowed_skill_ids=allowed_skill_ids,
    )


def _decision(binding: SkillTrustBinding, status: SkillTrustDecisionStatus) -> SkillTrustDecision:
    return SkillTrustDecision(status=status, binding=binding)


def _skill(
    *,
    name: str = "review-pr",
    source_bytes: bytes = b"same",
) -> RegisteredSkill:
    definition = _definition(name, source_bytes=source_bytes)
    return RegisteredSkill(skill_id=f"workspace:{name}", source=SkillSource.WORKSPACE, definition=definition)


def _definition(name: str, *, source_bytes: bytes, disabled: bool = False) -> SkillDefinition:
    return SkillDefinition.from_skill_file_bytes(
        name=name,
        description="Review pull requests.",
        instructions="# Instructions\n",
        skill_file_bytes=source_bytes,
        disabled=disabled,
    )
