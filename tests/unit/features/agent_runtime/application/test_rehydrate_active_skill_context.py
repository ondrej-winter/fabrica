"""Tests for fail-closed active skill context compaction rehydration."""

from fabrica.features.agent_runtime.application.dtos import (
    ActiveSkill,
    ActiveSkillCompactionState,
    ActiveSkillSet,
    LocalAgentContextBlock,
    LocalAgentRunCommand,
)
from fabrica.features.agent_runtime.application.use_cases import (
    ActiveSkillContextRehydrationStatus,
    RehydrateActiveSkillContext,
)


def test_compaction_preserves_active_skill_order_and_rehydrates_before_retrieved_context() -> None:
    active_skills = ActiveSkillSet(run_id="run-1", registry_snapshot_id="snapshot-1")
    active_skills.register(skill_id="workspace:first", revision="sha256:" + "a" * 64, instructions="first")
    active_skills.register(skill_id="global:second", revision="sha256:" + "b" * 64, instructions="second")

    state = RehydrateActiveSkillContext.compact(active_skills)
    result = RehydrateActiveSkillContext(max_total_context_chars=100).rehydrate(
        LocalAgentRunCommand(
            prompt="continue",
            context=(LocalAgentContextBlock(text="retrieved", label="search result"),),
        ),
        state=state,
        run_id="run-1",
        registry_snapshot_id="snapshot-1",
    )

    assert result.status is ActiveSkillContextRehydrationStatus.REHYDRATED
    assert result.command is not None
    assert [block.text for block in result.command.context] == ["first", "second", "retrieved"]
    assert [block.metadata["activation_order"] for block in result.command.context[:2]] == [0, 1]
    assert state.skills == active_skills.skills


def test_rehydration_rejects_missing_mismatched_and_malformed_active_state() -> None:
    rehydrator = RehydrateActiveSkillContext(max_total_context_chars=100)
    command = LocalAgentRunCommand(prompt="continue")
    malformed = ActiveSkillCompactionState(
        run_id="run-1",
        registry_snapshot_id="snapshot-1",
        skills=(
            ActiveSkill(
                skill_id="workspace:out-of-order",
                instruction_revision="sha256:" + "c" * 64,
                instructions="skill",
                activation_order=1,
                registry_snapshot_id="snapshot-1",
            ),
        ),
    )

    missing = rehydrator.rehydrate(command, state=None, run_id="run-1", registry_snapshot_id="snapshot-1")
    mismatched = rehydrator.rehydrate(
        command,
        state=malformed,
        run_id="other-run",
        registry_snapshot_id="snapshot-1",
    )
    invalid_order = rehydrator.rehydrate(command, state=malformed, run_id="run-1", registry_snapshot_id="snapshot-1")

    assert missing.status is ActiveSkillContextRehydrationStatus.MALFORMED_STATE
    assert mismatched.status is ActiveSkillContextRehydrationStatus.MALFORMED_STATE
    assert invalid_order.status is ActiveSkillContextRehydrationStatus.MALFORMED_STATE


def test_rehydration_fails_closed_when_required_active_skills_exceed_context_budget() -> None:
    state = ActiveSkillCompactionState(
        run_id="run-1",
        registry_snapshot_id="snapshot-1",
        skills=(
            ActiveSkill(
                skill_id="workspace:large",
                instruction_revision="sha256:" + "d" * 64,
                instructions="skill instructions",
                activation_order=0,
                registry_snapshot_id="snapshot-1",
            ),
        ),
    )

    result = RehydrateActiveSkillContext(max_total_context_chars=10).rehydrate(
        LocalAgentRunCommand(prompt="continue"),
        state=state,
        run_id="run-1",
        registry_snapshot_id="snapshot-1",
    )

    assert result.status is ActiveSkillContextRehydrationStatus.ACTIVE_SKILL_CONTEXT_OVERFLOW
