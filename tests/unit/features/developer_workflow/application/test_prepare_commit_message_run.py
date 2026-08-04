"""Tests for commit-message runtime command preparation."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    LoadedSkillContext,
    LocalAgentContextBlock,
    SelectedSkill,
)
from fabrica.features.agent_runtime.application.use_cases import LoadSkillContext
from fabrica.features.developer_workflow.application.dtos import (
    GitStagedChangesFailureCategory,
    GitStagedDiff,
)
from fabrica.features.developer_workflow.application.ports import GitStagedChangesLoadError
from fabrica.features.developer_workflow.application.use_cases import (
    DEFAULT_COMMIT_MESSAGE_SKILL_ID,
    PrepareCommitMessageRun,
)


@dataclass
class FakeStagedChangesLoader:
    diff: GitStagedDiff | None = None
    error: GitStagedChangesLoadError | None = None
    calls: int = 0

    def load(self) -> GitStagedDiff:
        return self.load_diff()

    def load_diff(self) -> GitStagedDiff:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.diff is None:
            msg = "no staged changes"
            raise GitStagedChangesLoadError(msg, category=GitStagedChangesFailureCategory.NO_STAGED_CHANGES)
        return self.diff


@dataclass
class FakeSkillContextLoader:
    calls: list[SelectedSkill] = field(default_factory=list)

    def load(self, selection: SelectedSkill) -> LoadedSkillContext:
        self.calls.append(selection)
        return LoadedSkillContext(skill_id=selection.skill_id, markdown=f"# {selection.skill_id}\n")


def test_prepare_commit_message_run_builds_prompt_with_default_skill_and_distinct_context() -> None:
    staged_loader = FakeStagedChangesLoader(diff=GitStagedDiff(text="diff --git a/file.py b/file.py\n"))
    skill_loader = FakeSkillContextLoader()

    command = PrepareCommitMessageRun(staged_loader, LoadSkillContext(skill_loader)).prepare()

    assert "evidence-first" in command.prompt
    assert "File-level evidence pass" in command.prompt
    assert "each staged file independently" in command.prompt
    assert "behavior, tests, docs, configuration, architecture, refactor, or maintenance" in command.prompt
    assert "Intent grouping pass" in command.prompt
    assert "dominant intent" in command.prompt
    assert "Conventional Commit synthesis pass" in command.prompt
    assert "apply the selected Agent Skill" in command.prompt
    assert "vague activity summary" in command.prompt
    assert "file-by-file changelog" in command.prompt
    assert "full per-file evidence report" in command.prompt
    assert "Summary:" in command.prompt
    assert "Rationale:" in command.prompt
    assert "Commit message:" in command.prompt
    assert "Do not use markdown headings" in command.prompt
    assert command.context == (
        LocalAgentContextBlock(
            text="diff --git a/file.py b/file.py\n",
            label="Git staged diff",
            metadata={"source": "git_staged_diff", "char_count": 31},
        ),
        LocalAgentContextBlock(
            text="# conventional-commits\n",
            label="Agent Skill: conventional-commits",
            metadata={"source": "agent_skill", "skill_id": "conventional-commits"},
        ),
    )
    assert skill_loader.calls == [SelectedSkill(skill_id=DEFAULT_COMMIT_MESSAGE_SKILL_ID)]


def test_prepare_commit_message_run_supports_skill_override() -> None:
    staged_loader = FakeStagedChangesLoader(diff=GitStagedDiff(text="diff --git a/file.py b/file.py\n"))
    skill_loader = FakeSkillContextLoader()

    PrepareCommitMessageRun(staged_loader, LoadSkillContext(skill_loader)).prepare(skill_id="team-commit-style")

    assert skill_loader.calls == [SelectedSkill(skill_id="team-commit-style")]


def test_prepare_commit_message_run_propagates_staged_changes_failure_before_skill_loading() -> None:
    staged_loader = FakeStagedChangesLoader(
        error=GitStagedChangesLoadError(
            "no staged changes",
            category=GitStagedChangesFailureCategory.NO_STAGED_CHANGES,
        ),
    )
    skill_loader = FakeSkillContextLoader()

    with pytest.raises(GitStagedChangesLoadError):
        PrepareCommitMessageRun(staged_loader, LoadSkillContext(skill_loader)).prepare()

    assert staged_loader.calls == 1
    assert skill_loader.calls == []
