"""Expose Version 1 Agent Skill activation as the model-facing ``skills`` tool."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    ActiveSkillSet,
    RegisteredToolOutcome,
    SkillActivationCommand,
    SkillActivationResult,
    SkillActivationStatus,
    SkillRegistrySnapshot,
    ToolArgumentValue,
    ToolDefinition,
    ToolExecutionContext,
    ToolMutationGuarantee,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.agent_runtime.application.use_cases import ActivateSkill

SKILLS_TOOL_NAME = "skills"
_MAX_SKILL_INVOCATION_CHARS = 256
_MAX_SKILL_ARGS_CHARS = 6_000
_TRUST_CLASSIFICATION = "configured_skill_instructions"
_ACTIVATION_ERROR_MESSAGES = {
    SkillActivationStatus.INVALID_INPUT: "skill invocation is invalid",
    SkillActivationStatus.SKILL_NOT_FOUND: "requested skill is not available",
    SkillActivationStatus.AMBIGUOUS_SKILL: "requested skill matches multiple available skills",
    SkillActivationStatus.SKILL_NOT_ALLOWED: "requested skill is not allowed for this run",
    SkillActivationStatus.SKILL_UNTRUSTED: "requested skill is not trusted for this run",
    SkillActivationStatus.INVALID_SKILL_DEFINITION: "requested skill definition is unavailable or changed",
    SkillActivationStatus.SKILL_LOAD_TIMEOUT: "skill activation timed out",
    SkillActivationStatus.SKILL_LOAD_CANCELLED: "skill activation was cancelled",
    SkillActivationStatus.INTERNAL_SKILL_ERROR: "skill activation could not be completed",
}


@dataclass(frozen=True, slots=True)
class SkillActivationToolContext:
    """Host-owned immutable registry and active state required by one skills tool."""

    workspace_identity: str
    run_id: str
    snapshot: SkillRegistrySnapshot
    active_skills: ActiveSkillSet
    allowed_skill_ids: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.active_skills.run_id != self.run_id:
            msg = "skills tool active state must belong to the configured run"
            raise ValueError(msg)
        if self.active_skills.registry_snapshot_id != self.snapshot.snapshot_id:
            msg = "skills tool active state must belong to the configured registry snapshot"
            raise ValueError(msg)
        if self.allowed_skill_ids is not None:
            object.__setattr__(self, "allowed_skill_ids", frozenset(self.allowed_skill_ids))


def _tool_definition(snapshot: SkillRegistrySnapshot) -> ToolDefinition:
    return ToolDefinition(
        name=SKILLS_TOOL_NAME,
        description=snapshot.catalog_description(),
        argument_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string", "minLength": 1, "maxLength": _MAX_SKILL_INVOCATION_CHARS},
                "args": {"type": ("string", "null"), "maxLength": _MAX_SKILL_ARGS_CHARS},
            },
            "required": ("skill",),
            "additionalProperties": False,
        },
    )


@dataclass(frozen=True, slots=True)
class SkillsRegisteredToolAdapter:
    """Validate model arguments and map activation results to structured tool content."""

    activator: ActivateSkill
    activation_context: SkillActivationToolContext

    async def handle(
        self,
        arguments: Mapping[str, ToolArgumentValue],
        context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        """Activate one registered skill or return a stable recoverable rejection."""
        try:
            skill, args = _activation_arguments(arguments)
        except (TypeError, ValueError) as err:
            return RegisteredToolOutcome.recoverable_rejection(error_code="INVALID_ARGUMENTS", error_message=str(err))

        result = await self.activator.activate(
            SkillActivationCommand(
                workspace_identity=self.activation_context.workspace_identity,
                run_id=self.activation_context.run_id,
                snapshot=self.activation_context.snapshot,
                skill=skill,
                args=args,
                allowed_skill_ids=self.activation_context.allowed_skill_ids,
            ),
            active_skills=self.activation_context.active_skills,
            cancellation=context.cancellation,
        )
        return _activation_outcome(result, self.activation_context.snapshot.snapshot_id)


def create_skills_registered_tool(
    activator: ActivateSkill,
    activation_context: SkillActivationToolContext,
) -> AsyncRegisteredTool:
    """Create one registry-snapshot-bound model-facing skills tool."""
    adapter = SkillsRegisteredToolAdapter(activator=activator, activation_context=activation_context)
    return AsyncRegisteredTool(definition=_tool_definition(activation_context.snapshot), handler=adapter.handle)


def _activation_arguments(arguments: Mapping[str, ToolArgumentValue]) -> tuple[str, str | None]:
    if set(arguments) - {"skill", "args"} or "skill" not in arguments:
        msg = "skills requires `skill` and accepts only nullable `args`"
        raise ValueError(msg)
    skill = arguments["skill"]
    args = arguments.get("args")
    if not isinstance(skill, str) or not skill:
        msg = "skills `skill` must be a non-empty string"
        raise ValueError(msg)
    if len(skill) > _MAX_SKILL_INVOCATION_CHARS:
        msg = "skills `skill` exceeds the maximum length"
        raise ValueError(msg)
    if args is not None and not isinstance(args, str):
        msg = "skills `args` must be a string or null"
        raise TypeError(msg)
    if isinstance(args, str) and len(args) > _MAX_SKILL_ARGS_CHARS:
        msg = "skills `args` exceeds the maximum length"
        raise ValueError(msg)
    return skill, args


def _activation_outcome(result: SkillActivationResult, snapshot_id: str) -> RegisteredToolOutcome:
    if result.status is SkillActivationStatus.ACTIVATED:
        active_skill = result.active_skill
        if active_skill is None or result.description is None or result.source is None:
            return _activation_rejection(SkillActivationStatus.INTERNAL_SKILL_ERROR, result)
        payload = {
            "success": True,
            "status": result.status.value,
            "skill": {
                "id": active_skill.skill_id,
                "name": active_skill.skill_id.split(":", maxsplit=1)[1],
                "description": result.description,
                "revision": active_skill.instruction_revision,
                "source": result.source.value,
                "registry_snapshot_id": snapshot_id,
            },
            "args": result.args,
            "instructions": active_skill.instructions,
            "trust": _TRUST_CLASSIFICATION,
        }
        return RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            content=(ToolTextContent(_serialize(payload)),),
        )
    if result.status is SkillActivationStatus.ALREADY_ACTIVE:
        active_skill = result.active_skill
        if active_skill is None:
            return _activation_rejection(SkillActivationStatus.INTERNAL_SKILL_ERROR, result)
        return RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            content=(
                ToolTextContent(
                    _serialize(
                        {
                            "success": True,
                            "status": result.status.value,
                            "skill": {"id": active_skill.skill_id, "revision": active_skill.instruction_revision},
                            "args": result.args,
                        },
                    ),
                ),
            ),
        )
    return _activation_rejection(result.status, result)


def _activation_rejection(
    status: SkillActivationStatus,
    result: SkillActivationResult,
) -> RegisteredToolOutcome:
    details = {"candidates": ",".join(result.candidates)} if result.candidates else None
    return RegisteredToolOutcome.recoverable_rejection(
        error_code=status.name,
        error_message=_ACTIVATION_ERROR_MESSAGES[status],
        details=details,
    )


def _serialize(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


__all__ = [
    "SKILLS_TOOL_NAME",
    "SkillActivationToolContext",
    "SkillsRegisteredToolAdapter",
    "create_skills_registered_tool",
]
