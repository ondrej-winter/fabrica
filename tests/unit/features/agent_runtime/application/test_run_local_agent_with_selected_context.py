"""Tests for selected-context local agent runtime orchestration."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillContext,
    LoadedSkillResourceContext,
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    SelectedSkill,
    SelectedSkillResource,
)
from fabrica.features.agent_runtime.application.ports import SkillContextLoadError
from fabrica.features.agent_runtime.application.use_cases import (
    LoadSkillContext,
    LoadSkillResourceContext,
    RunLocalAgentWithSelectedContext,
)


@dataclass
class FakeRuntime:
    """Test double for the local agent runtime port."""

    result: LocalAgentRunResult
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.result


@dataclass
class FakeSkillContextLoader:
    loaded_by_id: dict[str, LoadedSkillContext]

    def load(self, selection: SelectedSkill) -> LoadedSkillContext:
        try:
            return self.loaded_by_id[selection.skill_id]
        except KeyError as err:
            msg = "selected skill is unavailable"
            raise SkillContextLoadError(msg, skill_id=selection.skill_id, category="missing_skill") from err


@dataclass
class FakeSkillResourceContextLoader:
    loaded_by_id: dict[tuple[str, str], LoadedSkillResourceContext]

    def load(self, selection: SelectedSkillResource) -> LoadedSkillResourceContext:
        try:
            return self.loaded_by_id[(selection.skill_id, selection.resource_id)]
        except KeyError as err:
            msg = "selected skill resource is unavailable"
            raise SkillContextLoadError(
                msg,
                skill_id=selection.skill_id,
                category="missing_resource",
                metadata={"resource_id": selection.resource_id},
            ) from err


def test_selected_context_runtime_loads_context_before_running_local_agent() -> None:
    runtime = FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="pong"))
    use_case = RunLocalAgentWithSelectedContext(
        runtime=runtime,
        skill_context_loader=LoadSkillContext(
            loader=FakeSkillContextLoader(
                loaded_by_id={
                    "python-testing": LoadedSkillContext(
                        skill_id="python-testing",
                        markdown="# Python Testing",
                    ),
                },
            ),
        ),
        skill_resource_context_loader=LoadSkillResourceContext(
            loader=FakeSkillResourceContextLoader(
                loaded_by_id={
                    ("python-testing", "references/example.md"): LoadedSkillResourceContext(
                        skill_id="python-testing",
                        resource_id="references/example.md",
                        text="Use focused tests.",
                    ),
                },
            ),
        ),
    )

    result = use_case.run(
        LocalAgentRunCommand(prompt="Use context"),
        skill_selections=(SelectedSkill(skill_id="python-testing"),),
        resource_selections=(SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md"),),
    )

    assert result.succeeded
    assert runtime.calls == [
        LocalAgentRunCommand(
            prompt="Use context",
            context=(
                LocalAgentContextBlock(
                    text="# Python Testing",
                    label="Agent Skill: python-testing",
                    metadata={"source": "agent_skill", "skill_id": "python-testing"},
                ),
                LocalAgentContextBlock(
                    text="Use focused tests.",
                    label="Agent Skill Resource: python-testing/references/example.md",
                    metadata={
                        "source": "agent_skill_resource",
                        "skill_id": "python-testing",
                        "resource_id": "references/example.md",
                        "media_type": "text/plain",
                    },
                ),
            ),
        ),
    ]


def test_selected_context_runtime_requires_loader_for_selected_skills() -> None:
    use_case = RunLocalAgentWithSelectedContext(
        runtime=FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS)),
    )

    with pytest.raises(RuntimeError, match="selected skill context loader is not configured"):
        use_case.run(
            LocalAgentRunCommand(prompt="Use context"),
            skill_selections=(SelectedSkill(skill_id="python-testing"),),
        )
