"""Contracts and injected dependencies for agent-runtime CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from pathlib import Path

    from fabrica.features.agent_runtime.application.dtos import (
        LocalAgentRunResult,
        SkillScriptExecutionResult,
        SkillScriptPolicyEvaluationResult,
    )
    from fabrica.features.agent_runtime.application.ports import (
        LocalAgentRuntime,
        SelectedContextLocalAgentRuntime,
        SkillScriptPolicyEvaluator,
        SkillScriptRunner,
    )


class RunResultWriter(Protocol):
    """Writer for one local agent runtime result."""

    def __call__(self, result: LocalAgentRunResult, *, stdout: TextIO, stderr: TextIO) -> int:
        """Write a local runtime result and return a process exit code."""


class EvidenceWriter(Protocol):
    """Writer for requested model evidence after command output."""

    def __call__(
        self,
        result: LocalAgentRunResult,
        *,
        include_usage: bool,
        include_prices: bool,
        stdout: TextIO,
    ) -> None:
        """Write model evidence selected by global CLI options."""


class ScriptPolicyResultWriter(Protocol):
    """Writer for one selected script policy result."""

    def __call__(self, result: SkillScriptPolicyEvaluationResult, *, stdout: TextIO, stderr: TextIO) -> int:
        """Write a selected script policy result and return a process exit code."""


class ScriptExecutionResultWriter(Protocol):
    """Writer for one selected script execution result."""

    def __call__(self, result: SkillScriptExecutionResult, *, stdout: TextIO, stderr: TextIO) -> int:
        """Write a selected script execution result and return a process exit code."""


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliOptions:
    """Product CLI option values consumed by agent-runtime commands."""

    print_usage: bool = False
    print_prices: bool = False
    verbose_diagnostics: bool = False
    skill_roots: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliDependencies:
    """Injected dependencies for agent-runtime CLI commands."""

    runtime: LocalAgentRuntime | None = None
    selected_context_runtime: SelectedContextLocalAgentRuntime | None = None
    script_policy_evaluator: SkillScriptPolicyEvaluator | None = None
    script_executor: SkillScriptRunner | None = None


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliWriters:
    """Injected output writers for agent-runtime CLI commands."""

    run_result: RunResultWriter
    evidence: EvidenceWriter
    script_policy_result: ScriptPolicyResultWriter
    script_execution_result: ScriptExecutionResultWriter


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliStreams:
    """Normalized CLI input/output streams for agent-runtime commands."""

    stdout: TextIO
    stderr: TextIO
