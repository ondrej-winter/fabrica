"""Contracts and injected dependencies for agent-runtime CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from pathlib import Path

    from fabrica.features.agent_runtime.application.dtos import (
        LocalAgentRunCommand,
        LocalAgentRunResult,
        SelectedSkill,
        SelectedSkillResource,
        SkillScriptExecutionCommand,
        SkillScriptExecutionResult,
        SkillScriptPolicyEvaluationCommand,
        SkillScriptPolicyEvaluationResult,
    )


class LocalAgentRuntime(Protocol):
    """Protocol for the runtime use case consumed by the CLI adapter."""

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command."""


class CommandAugmenter(Protocol):
    """Protocol for selected skill/resource command augmentation."""

    def __call__(
        self,
        command: LocalAgentRunCommand,
        skill_selections: tuple[SelectedSkill, ...],
        resource_selections: tuple[SelectedSkillResource, ...],
        *,
        skill_roots: tuple[Path, ...],
        verbose_diagnostics: bool,
    ) -> LocalAgentRunCommand:
        """Return a command augmented with explicitly selected context."""


class ScriptPolicyEvaluator(Protocol):
    """Protocol for selected skill script policy evaluation consumed by the CLI adapter."""

    def evaluate(self, command: SkillScriptPolicyEvaluationCommand) -> SkillScriptPolicyEvaluationResult:
        """Evaluate selected script policy without executing the script."""


class ScriptExecutor(Protocol):
    """Protocol for selected skill script execution consumed by the CLI adapter."""

    def execute(self, command: SkillScriptExecutionCommand) -> SkillScriptExecutionResult:
        """Execute one selected skill script through policy-gated application boundaries."""


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliDependencies:
    """Injected dependencies for agent-runtime CLI commands."""

    runtime: LocalAgentRuntime | None = None
    command_augmenter: CommandAugmenter | None = None
    script_policy_evaluator: ScriptPolicyEvaluator | None = None
    script_executor: ScriptExecutor | None = None


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliStreams:
    """Normalized CLI input/output streams for agent-runtime commands."""

    stdout: TextIO
    stderr: TextIO
