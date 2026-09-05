"""Tests for the model-facing Version 1 skills registered-tool adapter."""

import asyncio
import json
from dataclasses import dataclass

from fabrica.features.agent_runtime.adapters.inbound.registered_tool import (
    SKILLS_TOOL_NAME,
    SkillActivationToolContext,
    create_skills_registered_tool,
)
from fabrica.features.agent_runtime.application.dtos import (
    ActiveSkillSet,
    RegisteredSkill,
    SkillDefinition,
    SkillRegistrySnapshot,
    SkillSource,
    SkillTrustBinding,
    SkillTrustDecision,
    SkillTrustDecisionStatus,
    ToolExecutionContext,
    ToolOutcomeStatus,
    ToolTextContent,
    canonical_tool_arguments_digest,
)
from fabrica.features.agent_runtime.application.use_cases import ActivateSkill, EvaluateSkillTrust


def test_skills_tool_exposes_only_skill_and_nullable_args_with_a_bounded_catalog() -> None:
    snapshot = _snapshot()

    tool = create_skills_registered_tool(_activator(snapshot), _context(snapshot))

    assert tool.definition.name == SKILLS_TOOL_NAME
    assert tool.definition.argument_schema == {
        "type": "object",
        "properties": {
            "skill": {"type": "string", "minLength": 1, "maxLength": 256},
            "args": {"type": ("string", "null"), "maxLength": 6000},
        },
        "required": ("skill",),
        "additionalProperties": False,
    }
    assert len(tool.definition.description) <= 1_000  # noqa: PLR2004
    assert "workspace:review-pr" in tool.definition.description


def test_skills_tool_returns_complete_activation_instructions_as_one_structured_content_part() -> None:
    snapshot = _snapshot(instructions="# Review\n\nInspect the diff before writing findings.\n")
    tool = create_skills_registered_tool(_activator(snapshot), _context(snapshot))
    arguments = {"skill": "review-pr", "args": '<pr number="123">'}

    outcome = asyncio.run(tool.handler(arguments, _tool_context(arguments)))

    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert outcome.result_text is None
    assert len(outcome.content) == 1
    assert isinstance(outcome.content[0], ToolTextContent)
    payload = json.loads(outcome.content[0].text)
    assert payload == {
        "args": '<pr number="123">',
        "instructions": "# Review\n\nInspect the diff before writing findings.\n",
        "skill": {
            "description": "Review pull requests.",
            "id": "workspace:review-pr",
            "name": "review-pr",
            "registry_snapshot_id": "snapshot-1",
            "revision": snapshot.skills[0].revision,
            "source": "workspace",
        },
        "status": "activated",
        "success": True,
        "trust": "configured_skill_instructions",
    }


def test_skills_tool_returns_idempotent_metadata_without_reinjecting_instructions() -> None:
    snapshot = _snapshot()
    context = _context(snapshot)
    tool = create_skills_registered_tool(_activator(snapshot), context)
    arguments = {"skill": "workspace:review-pr", "args": "second"}

    asyncio.run(tool.handler({"skill": "review-pr"}, _tool_context({"skill": "review-pr"})))
    outcome = asyncio.run(tool.handler(arguments, _tool_context(arguments)))

    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert len(outcome.content) == 1
    assert isinstance(outcome.content[0], ToolTextContent)
    assert json.loads(outcome.content[0].text) == {
        "args": "second",
        "skill": {"id": "workspace:review-pr", "revision": snapshot.skills[0].revision},
        "status": "already_active",
        "success": True,
    }


def test_skills_tool_rejects_malformed_missing_ambiguous_and_denied_invocations_without_state_changes() -> None:
    review = _skill("review-pr", "Review pull requests.")
    global_review = _skill("review-pr", "Review global pull requests.", source=SkillSource.GLOBAL)
    snapshot = SkillRegistrySnapshot.create(snapshot_id="snapshot-1", skills=(review, global_review))
    context = _context(snapshot, allowed_skill_ids=frozenset({"workspace:review-pr"}))
    tool = create_skills_registered_tool(_activator(snapshot), context)

    outcomes = [
        asyncio.run(tool.handler({}, _tool_context({}))),
        asyncio.run(tool.handler({"skill": "missing"}, _tool_context({"skill": "missing"}))),
        asyncio.run(tool.handler({"skill": "review-pr"}, _tool_context({"skill": "review-pr"}))),
        asyncio.run(
            tool.handler(
                {"skill": "global:review-pr"},
                _tool_context({"skill": "global:review-pr"}),
            ),
        ),
    ]

    assert [outcome.error_code for outcome in outcomes] == [
        "INVALID_ARGUMENTS",
        "SKILL_NOT_FOUND",
        "AMBIGUOUS_SKILL",
        "SKILL_NOT_ALLOWED",
    ]
    assert context.active_skills.skills == ()


@dataclass(frozen=True, slots=True)
class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        await asyncio.Event().wait()


@dataclass(frozen=True, slots=True)
class _TrustedLookup:
    def get_decision(self, binding: SkillTrustBinding) -> SkillTrustDecision:
        return SkillTrustDecision(status=SkillTrustDecisionStatus.TRUSTED, binding=binding)


@dataclass(frozen=True, slots=True)
class _SnapshotRevisionLoader:
    snapshot: SkillRegistrySnapshot

    def load_registered(self, skill: RegisteredSkill) -> SkillDefinition:
        return next(candidate.definition for candidate in self.snapshot.skills if candidate.skill_id == skill.skill_id)


def _activator(snapshot: SkillRegistrySnapshot) -> ActivateSkill:
    return ActivateSkill(EvaluateSkillTrust(_TrustedLookup(), _SnapshotRevisionLoader(snapshot)))


def _context(
    snapshot: SkillRegistrySnapshot,
    *,
    allowed_skill_ids: frozenset[str] | None = None,
) -> SkillActivationToolContext:
    return SkillActivationToolContext(
        workspace_identity="workspace-1",
        run_id="run-1",
        snapshot=snapshot,
        active_skills=ActiveSkillSet(run_id="run-1", registry_snapshot_id=snapshot.snapshot_id),
        allowed_skill_ids=allowed_skill_ids,
    )


def _tool_context(arguments: dict[str, str]) -> ToolExecutionContext:
    return ToolExecutionContext(
        call_id="call-1",
        argument_digest=canonical_tool_arguments_digest(arguments),
        cancellation=_NeverCancelled(),
    )


def _snapshot(*, instructions: str = "# Review\n") -> SkillRegistrySnapshot:
    skill = _skill("review-pr", "Review pull requests.", instructions)
    return SkillRegistrySnapshot.create(snapshot_id="snapshot-1", skills=(skill,))


def _skill(
    name: str,
    description: str,
    instructions: str = "# Review\n",
    *,
    source: SkillSource = SkillSource.WORKSPACE,
) -> RegisteredSkill:
    definition = SkillDefinition.from_skill_file_bytes(
        name=name,
        description=description,
        instructions=instructions,
        skill_file_bytes=f"{source.value}:{name}:{instructions}".encode(),
    )
    return RegisteredSkill(skill_id=f"{source.value}:{name}", source=source, definition=definition)
