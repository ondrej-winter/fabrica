"""Use case for atomic, revision-pinned Version 1 Agent Skill activation."""

import asyncio
from dataclasses import replace

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_SKILL_LOAD_TIMEOUT_SECONDS,
    ActiveSkill,
    ActiveSkillSet,
    RegisteredSkill,
    SkillActivationAuditEvent,
    SkillActivationCommand,
    SkillActivationResult,
    SkillActivationStatus,
    SkillResolutionStatus,
    SkillTrustEvaluationCommand,
    SkillTrustEvaluationResult,
    SkillTrustEvaluationStatus,
    ToolCancellationSignal,
)
from fabrica.features.agent_runtime.application.ports import SkillActivationAuditRecorder, SkillTrustEvaluator


class ActivateSkill:
    """Resolve, verify, and atomically activate one skill in a run-scoped active set."""

    def __init__(
        self,
        trust_evaluator: SkillTrustEvaluator,
        *,
        timeout_seconds: float = DEFAULT_SKILL_LOAD_TIMEOUT_SECONDS,
        audit_recorder: SkillActivationAuditRecorder | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            msg = "skill activation timeout must be positive"
            raise ValueError(msg)
        self._trust_evaluator = trust_evaluator
        self._timeout_seconds = timeout_seconds
        self._audit_recorder = audit_recorder

    async def activate(
        self,
        command: SkillActivationCommand,
        *,
        active_skills: ActiveSkillSet,
        cancellation: ToolCancellationSignal,
    ) -> SkillActivationResult:
        """Activate only a verified snapshot definition while preserving atomic active state."""
        precondition_error = _precondition_error(command, active_skills, cancellation)
        if precondition_error is not None:
            return precondition_error
        skill_or_result = self._resolve_for_activation(command, active_skills)
        if isinstance(skill_or_result, SkillActivationResult):
            return skill_or_result

        evaluated_or_result = await self._evaluate_with_cancellation(
            SkillTrustEvaluationCommand(
                workspace_identity=command.workspace_identity,
                run_id=command.run_id,
                skill=skill_or_result,
                allowed_skill_ids=command.allowed_skill_ids,
            ),
            cancellation=cancellation,
        )
        if isinstance(evaluated_or_result, SkillActivationResult):
            return replace(evaluated_or_result, args=command.args)
        return self._register_verified_skill(
            command,
            active_skills,
            skill_or_result,
            evaluated_or_result,
            cancellation,
        )

    def _resolve_for_activation(
        self,
        command: SkillActivationCommand,
        active_skills: ActiveSkillSet,
    ) -> RegisteredSkill | SkillActivationResult:
        try:
            resolution = command.snapshot.resolve(command.skill)
        except TypeError, ValueError:  # pragma: no cover - validated command snapshot resolution is total.
            return _result(SkillActivationStatus.INVALID_INPUT, command)

        resolution_error = _resolution_error(resolution.status, resolution.candidates, command)
        if resolution_error is not None:
            return resolution_error
        skill = resolution.skill
        if skill is None:  # pragma: no cover - FOUND SkillResolution requires a skill by DTO invariant.
            return _result(SkillActivationStatus.INTERNAL_SKILL_ERROR, command)
        active_skill = _active_skill_for(active_skills, skill)
        if active_skill is not None:
            return SkillActivationResult(
                status=SkillActivationStatus.ALREADY_ACTIVE,
                args=command.args,
                active_skill=active_skill,
                source=skill.source,
            )
        return skill

    def _register_verified_skill(
        self,
        command: SkillActivationCommand,
        active_skills: ActiveSkillSet,
        skill: RegisteredSkill,
        evaluation: SkillTrustEvaluationResult,
        cancellation: ToolCancellationSignal,
    ) -> SkillActivationResult:
        activation_error = _activation_error_from_evaluation(evaluation, command)
        if activation_error is not None:
            return activation_error
        if cancellation.is_cancelled:
            return _result(SkillActivationStatus.SKILL_LOAD_CANCELLED, command)
        definition = evaluation.definition
        if definition is None:  # pragma: no cover - APPROVED trust evaluations require a definition.
            return _result(SkillActivationStatus.INTERNAL_SKILL_ERROR, command)
        try:
            active_skill = active_skills.register(
                skill_id=skill.skill_id,
                revision=definition.revision,
                instructions=definition.instructions,
            )
        except ValueError:
            return _result(SkillActivationStatus.INTERNAL_SKILL_ERROR, command)

        if self._audit_recorder is not None:
            self._audit_recorder.record(
                SkillActivationAuditEvent(
                    skill_id=skill.skill_id,
                    revision=definition.revision,
                    source=skill.source,
                    reason=command.reason,
                    run_id=command.run_id,
                    registry_snapshot_id=command.snapshot.snapshot_id,
                )
            )
        return SkillActivationResult(
            status=SkillActivationStatus.ACTIVATED,
            args=command.args,
            active_skill=active_skill,
            description=definition.description,
            source=skill.source,
        )

    async def _evaluate_with_cancellation(
        self,
        command: SkillTrustEvaluationCommand,
        *,
        cancellation: ToolCancellationSignal,
    ) -> SkillActivationResult | SkillTrustEvaluationResult:
        evaluation_task = asyncio.create_task(asyncio.to_thread(self._trust_evaluator.evaluate, command))
        cancellation_task = asyncio.create_task(cancellation.wait_until_cancelled())
        try:
            done, _ = await asyncio.wait(
                (evaluation_task, cancellation_task),
                timeout=self._timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                return SkillActivationResult(status=SkillActivationStatus.SKILL_LOAD_TIMEOUT, args=None)
            if cancellation_task in done or cancellation.is_cancelled:
                return SkillActivationResult(status=SkillActivationStatus.SKILL_LOAD_CANCELLED, args=None)
            return evaluation_task.result()
        except OSError, RuntimeError, ValueError:
            return SkillActivationResult(status=SkillActivationStatus.INTERNAL_SKILL_ERROR, args=None)
        finally:
            cancellation_task.cancel()
            evaluation_task.cancel()


def _active_skill_for(active_skills: ActiveSkillSet, skill: RegisteredSkill) -> ActiveSkill | None:
    return next(
        (
            active
            for active in active_skills.skills
            if active.skill_id == skill.skill_id and active.instruction_revision == skill.revision
        ),
        None,
    )


def _activation_error_from_evaluation(
    evaluation: SkillTrustEvaluationResult,
    command: SkillActivationCommand,
) -> SkillActivationResult | None:
    status = {
        SkillTrustEvaluationStatus.NOT_ALLOWED: SkillActivationStatus.SKILL_NOT_ALLOWED,
        SkillTrustEvaluationStatus.UNTRUSTED: SkillActivationStatus.SKILL_UNTRUSTED,
        SkillTrustEvaluationStatus.REVISION_MISMATCH: SkillActivationStatus.INVALID_SKILL_DEFINITION,
        SkillTrustEvaluationStatus.DEFINITION_UNAVAILABLE: SkillActivationStatus.INVALID_SKILL_DEFINITION,
    }.get(evaluation.status)
    return _result(status, command) if status is not None else None


def _resolution_error(
    status: SkillResolutionStatus,
    candidates: tuple[str, ...],
    command: SkillActivationCommand,
) -> SkillActivationResult | None:
    if status is SkillResolutionStatus.MISSING:
        return _result(SkillActivationStatus.SKILL_NOT_FOUND, command)
    if status is SkillResolutionStatus.AMBIGUOUS:
        return SkillActivationResult(
            status=SkillActivationStatus.AMBIGUOUS_SKILL,
            args=command.args,
            candidates=candidates,
        )
    return None


def _result(status: SkillActivationStatus, command: SkillActivationCommand) -> SkillActivationResult:
    return SkillActivationResult(status=status, args=command.args)


def _precondition_error(
    command: SkillActivationCommand,
    active_skills: ActiveSkillSet,
    cancellation: ToolCancellationSignal,
) -> SkillActivationResult | None:
    if active_skills.run_id != command.run_id or active_skills.registry_snapshot_id != command.snapshot.snapshot_id:
        return _result(SkillActivationStatus.INTERNAL_SKILL_ERROR, command)
    if cancellation.is_cancelled:
        return _result(SkillActivationStatus.SKILL_LOAD_CANCELLED, command)
    return None
