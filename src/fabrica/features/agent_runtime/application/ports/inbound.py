"""Inbound application ports for local agent runtime use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
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
    """Inbound port for running one local agent command."""

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command."""


class SelectedContextLocalAgentRuntime(Protocol):
    """Inbound port for running a local agent with explicitly selected context."""

    def run(
        self,
        command: LocalAgentRunCommand,
        *,
        skill_selections: tuple[SelectedSkill, ...] = (),
        resource_selections: tuple[SelectedSkillResource, ...] = (),
    ) -> LocalAgentRunResult:
        """Run one local agent command with selected skill/resource context."""


class SkillScriptPolicyEvaluator(Protocol):
    """Inbound port for selected skill script policy evaluation."""

    def evaluate(self, command: SkillScriptPolicyEvaluationCommand) -> SkillScriptPolicyEvaluationResult:
        """Evaluate selected script policy without executing the script."""


class SkillScriptRunner(Protocol):
    """Inbound port for policy-gated selected skill script execution."""

    def execute(self, command: SkillScriptExecutionCommand) -> SkillScriptExecutionResult:
        """Execute one selected skill script through application boundaries."""
