"""Residual branch coverage for bootstrap composition helpers."""

import asyncio
from dataclasses import dataclass, field

import pytest

from fabrica.bootstrap.composition import tool_loop, user_interaction
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    RuntimeObservation,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.agent_runtime.application.use_cases import (
    ActiveSkillContextRehydrationResult,
    ActiveSkillContextRehydrationStatus,
)
from fabrica.features.user_interaction.application.dtos import InteractionOwner


def test_active_skill_compaction_options_require_identifiers() -> None:
    rehydrator = _Rehydrator(ActiveSkillContextRehydrationResult(ActiveSkillContextRehydrationStatus.MALFORMED_STATE))

    with pytest.raises(ValueError, match="run ID"):
        tool_loop.ActiveSkillCompactionOptions(
            rehydrator=rehydrator,  # ty: ignore[invalid-argument-type]
            run_id="",
            registry_snapshot_id="snapshot-1",
        )
    with pytest.raises(ValueError, match="registry snapshot ID"):
        tool_loop.ActiveSkillCompactionOptions(
            rehydrator=rehydrator,  # ty: ignore[invalid-argument-type]
            run_id="run-1",
            registry_snapshot_id="",
        )


def test_tool_loop_runtime_rejects_rehydrated_status_without_command() -> None:
    runtime = tool_loop.ToolLoopRuntime(
        runner=_Runner(),  # ty: ignore[invalid-argument-type]
        available_tools=(),
        active_skill_compaction=tool_loop.ActiveSkillCompactionOptions(
            rehydrator=_Rehydrator(  # ty: ignore[invalid-argument-type]
                ActiveSkillContextRehydrationResult(ActiveSkillContextRehydrationStatus.REHYDRATED),
            ),
            run_id="run-1",
            registry_snapshot_id="snapshot-1",
        ),
    )

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Continue")))

    assert result.status is ToolLoopRunStatus.ACTIVE_SKILL_CONTEXT_MALFORMED


def test_model_driven_runtime_prefixes_preparation_observations() -> None:
    runner = _Runner(result=ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS, output_text="done"))
    runtime = tool_loop.ModelDrivenSkillRuntime(
        runner=runner,  # ty: ignore[invalid-argument-type]
        context_options=tool_loop.SkillContextAugmentationOptions(),
        tool_preparation=tool_loop.SkillToolPreparationResult(
            observations=(RuntimeObservation(message="tool preparation warning"),),
        ),
        registered_tools=(),
    )

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Continue")))

    assert [observation.message for observation in result.observations] == ["tool preparation warning"]


def test_interactive_run_delegates_question_and_owner_cancellation() -> None:
    manager = _InteractionManager()
    run = user_interaction.InteractiveToolLoopRun(
        _runtime=_Runtime(),  # ty: ignore[invalid-argument-type]
        _interaction_manager=manager,  # ty: ignore[invalid-argument-type]
        owner=InteractionOwner("interaction_test"),
    )

    asyncio.run(run.cancel_question("question-1"))
    asyncio.run(run.cancel())

    assert manager.cancelled_questions == [(run.owner, "question-1")]
    assert manager.cancelled_owners == [run.owner]


def test_interactive_terminal_hook_ignores_non_owner_context_values() -> None:
    runtime = user_interaction.create_interactive_tool_loop_runtime(
        model=object(),  # ty: ignore[invalid-argument-type]
        transport=object(),  # ty: ignore[invalid-argument-type]
    )
    hook = runtime._runtime.runner._terminal_hooks[0]  # noqa: SLF001

    asyncio.run(hook({"interaction_owner": "not-an-owner"}))


@dataclass
class _Rehydrator:
    result: ActiveSkillContextRehydrationResult

    def rehydrate(self, *_args: object, **_kwargs: object) -> ActiveSkillContextRehydrationResult:
        return self.result


@dataclass
class _Runner:
    result: ToolLoopRunResult = field(default_factory=lambda: ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS))

    async def run(self, *_args: object, **_kwargs: object) -> ToolLoopRunResult:
        return self.result


class _Runtime:
    async def run(self, *_args: object, **_kwargs: object) -> ToolLoopRunResult:
        return ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS)


@dataclass
class _InteractionManager:
    cancelled_questions: list[tuple[InteractionOwner, str]] = field(default_factory=list)
    cancelled_owners: list[InteractionOwner] = field(default_factory=list)

    async def cancel(self, owner: InteractionOwner, question_id: str) -> None:
        self.cancelled_questions.append((owner, question_id))

    async def cancel_owner(self, owner: InteractionOwner) -> None:
        self.cancelled_owners.append(owner)
