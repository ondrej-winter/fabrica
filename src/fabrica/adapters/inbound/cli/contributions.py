"""Contribution contracts for the product CLI shell."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.options import CliGlobalOptions
    from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
        CommandAugmenter,
        LocalAgentRuntime,
        ScriptExecutor,
        ScriptPolicyEvaluator,
    )
    from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
        CommitMessageWorkflowRunner,
        ConfirmedCommitWorkflowRunner,
    )


type CommandRegistrar = Callable[[argparse._SubParsersAction[argparse.ArgumentParser]], None]  # noqa: SLF001
type ContributionRunner = Callable[[object, "CliExecutionContext"], int]


@dataclass(frozen=True, slots=True)
class CliCommandDependencies:
    """Product CLI dependency overrides for deterministic tests and composition."""

    runtime: LocalAgentRuntime | None = None
    command_augmenter: CommandAugmenter | None = None
    commit_message_workflow: CommitMessageWorkflowRunner | None = None
    confirmed_commit_workflow: ConfirmedCommitWorkflowRunner | None = None
    script_policy_evaluator: ScriptPolicyEvaluator | None = None
    script_executor: ScriptExecutor | None = None


@dataclass(frozen=True, slots=True)
class CliExecutionContext:
    """Shared execution context passed from the product CLI shell to one contribution."""

    global_options: CliGlobalOptions
    dependencies: CliCommandDependencies
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


@dataclass(frozen=True, slots=True)
class CliContribution:
    """One feature-owned command contribution aggregated by the product CLI."""

    name: str
    command_types: tuple[type[object], ...]
    register_commands: CommandRegistrar
    run_command: ContributionRunner

    def can_handle(self, command: object) -> bool:
        """Return whether this contribution owns the parsed command."""
        return isinstance(command, self.command_types)
