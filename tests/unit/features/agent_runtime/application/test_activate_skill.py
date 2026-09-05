"""Tests for atomic, revision-pinned Version 1 Agent Skill activation."""

import asyncio
import time
from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    ActiveSkillSet,
    RegisteredSkill,
    SkillActivationAuditEvent,
    SkillActivationCommand,
    SkillActivationReason,
    SkillActivationStatus,
    SkillDefinition,
    SkillRegistrySnapshot,
    SkillSource,
    SkillTrustBinding,
    SkillTrustDecision,
    SkillTrustDecisionStatus,
    SkillTrustEvaluationCommand,
    SkillTrustEvaluationResult,
)
from fabrica.features.agent_runtime.application.use_cases import ActivateSkill, EvaluateSkillTrust


def test_activation_registers_verified_instructions_and_audits_without_arguments() -> None:
    async def scenario() -> None:
        skill = _skill()
        audit = _AuditRecorder()
        result = await _activator(skill, audit_recorder=audit).activate(
            _command(skill, args='<args token="secret">123</args>'),
            active_skills=_active_skills(),
            cancellation=_Cancellation(),
        )

        assert result.status is SkillActivationStatus.ACTIVATED
        assert result.args == '<args token="secret">123</args>'
        assert result.active_skill is not None
        assert result.active_skill.instructions == "# Review\n"
        assert audit.events[0].skill_id == "workspace:review-pr"
        assert audit.events[0].reason is SkillActivationReason.MODEL_SELECTED
        assert "secret" not in repr(audit.events[0])

    asyncio.run(scenario())


def test_activation_is_idempotent_for_the_same_skill_revision_without_reinjection() -> None:
    async def scenario() -> None:
        skill = _skill()
        active_skills = _active_skills()
        activator = _activator(skill)

        first = await activator.activate(_command(skill), active_skills=active_skills, cancellation=_Cancellation())
        second = await activator.activate(
            _command(skill, args="second invocation"), active_skills=active_skills, cancellation=_Cancellation()
        )

        assert first.status is SkillActivationStatus.ACTIVATED
        assert second.status is SkillActivationStatus.ALREADY_ACTIVE
        assert second.args == "second invocation"
        assert len(active_skills.skills) == 1

    asyncio.run(scenario())


def test_failed_resolution_and_policy_checks_leave_active_state_unchanged() -> None:
    async def scenario() -> None:
        skill = _skill()
        active_skills = _active_skills()
        for activator, command, expected in (
            (_activator(skill), _command(skill, requested_skill="missing"), SkillActivationStatus.SKILL_NOT_FOUND),
            (
                _activator(skill),
                _command(skill, allowed_skill_ids=frozenset({"global:commit"})),
                SkillActivationStatus.SKILL_NOT_ALLOWED,
            ),
            (
                _activator(skill, trust_status=SkillTrustDecisionStatus.DENIED),
                _command(skill),
                SkillActivationStatus.SKILL_UNTRUSTED,
            ),
        ):
            result = await activator.activate(command, active_skills=active_skills, cancellation=_Cancellation())

            assert result.status is expected
            assert active_skills.skills == ()

    asyncio.run(scenario())


def test_ambiguous_skill_returns_candidates_without_changing_active_state() -> None:
    async def scenario() -> None:
        workspace_skill = _skill()
        snapshot = SkillRegistrySnapshot.create(
            snapshot_id="snapshot-1",
            skills=(
                _skill(source=SkillSource.GLOBAL),
                workspace_skill,
            ),
        )
        command = SkillActivationCommand(
            workspace_identity="workspace-1", run_id="run-1", snapshot=snapshot, skill="review-pr"
        )
        result = await _activator(workspace_skill).activate(
            command, active_skills=_active_skills(), cancellation=_Cancellation()
        )

        assert result.status is SkillActivationStatus.AMBIGUOUS_SKILL
        assert result.candidates == ("global:review-pr", "workspace:review-pr")

    asyncio.run(scenario())


def test_cancelled_or_timed_out_activation_never_registers_state() -> None:
    async def scenario() -> None:
        skill = _skill()
        cancelled = await _activator(skill).activate(
            _command(skill), active_skills=_active_skills(), cancellation=_Cancellation(cancelled=True)
        )
        blocking = _BlockingTrustEvaluator()
        timed_out_set = _active_skills()
        timed_out = await ActivateSkill(blocking, timeout_seconds=0.001).activate(
            _command(skill), active_skills=timed_out_set, cancellation=_Cancellation()
        )

        assert cancelled.status is SkillActivationStatus.SKILL_LOAD_CANCELLED
        assert timed_out.status is SkillActivationStatus.SKILL_LOAD_TIMEOUT
        assert timed_out_set.skills == ()

    asyncio.run(scenario())


@dataclass(slots=True)
class _Cancellation:
    cancelled: bool = False
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled

    async def wait_until_cancelled(self) -> None:
        await self._event.wait()


@dataclass(slots=True)
class _AuditRecorder:
    events: list[SkillActivationAuditEvent] = field(default_factory=list)

    def record(self, event: SkillActivationAuditEvent) -> None:
        self.events.append(event)


class _BlockingTrustEvaluator:
    def evaluate(self, command: SkillTrustEvaluationCommand) -> SkillTrustEvaluationResult:
        del command
        time.sleep(0.02)
        msg = "activation timeout should win"
        raise AssertionError(msg)


def _activator(
    skill: RegisteredSkill,
    *,
    audit_recorder: _AuditRecorder | None = None,
    trust_status: SkillTrustDecisionStatus = SkillTrustDecisionStatus.TRUSTED,
) -> ActivateSkill:
    evaluator = EvaluateSkillTrust(
        _TrustLookup(SkillTrustDecision(status=trust_status, binding=_binding(skill))),
        _RevisionLoader(skill.definition),
    )
    return ActivateSkill(evaluator, audit_recorder=audit_recorder)


def _command(
    skill: RegisteredSkill,
    *,
    requested_skill: str = "workspace:review-pr",
    args: str | None = None,
    allowed_skill_ids: frozenset[str] | None = None,
) -> SkillActivationCommand:
    return SkillActivationCommand(
        workspace_identity="workspace-1",
        run_id="run-1",
        snapshot=SkillRegistrySnapshot.create(snapshot_id="snapshot-1", skills=(skill,)),
        skill=requested_skill,
        args=args,
        allowed_skill_ids=allowed_skill_ids,
    )


@dataclass(slots=True)
class _TrustLookup:
    decision: SkillTrustDecision

    def get_decision(self, binding: SkillTrustBinding) -> SkillTrustDecision:
        if self.decision.binding == binding:
            return self.decision
        return SkillTrustDecision(SkillTrustDecisionStatus.DENIED, binding)


@dataclass(slots=True)
class _RevisionLoader:
    definition: SkillDefinition

    def load_registered(self, skill: RegisteredSkill) -> SkillDefinition:
        del skill
        return self.definition


def _active_skills() -> ActiveSkillSet:
    return ActiveSkillSet(run_id="run-1", registry_snapshot_id="snapshot-1")


def _binding(skill: RegisteredSkill) -> SkillTrustBinding:
    return SkillTrustBinding.from_registered_skill(workspace_identity="workspace-1", run_id="run-1", skill=skill)


def _skill(*, source: SkillSource = SkillSource.WORKSPACE) -> RegisteredSkill:
    definition = SkillDefinition.from_skill_file_bytes(
        name="review-pr",
        description="Review pull requests.",
        instructions="# Review\n",
        skill_file_bytes=f"{source.value}:review-pr".encode(),
    )
    return RegisteredSkill(skill_id=f"{source.value}:review-pr", source=source, definition=definition)
