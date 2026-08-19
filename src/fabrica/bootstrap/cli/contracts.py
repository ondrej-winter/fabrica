"""Contracts for bootstrap-owned product CLI composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fabrica.features.agent_runtime.application.ports import (
        LocalAgentRuntime,
        SelectedContextLocalAgentRuntime,
        SkillScriptPolicyEvaluator,
        SkillScriptRunner,
    )
    from fabrica.features.developer_workflow.application.ports import (
        CommitMessageWorkflowRunner,
        ConfirmedCommitWorkflowRunner,
    )


@dataclass(frozen=True, slots=True)
class CliDependencyOverrides:
    """Optional test/composition overrides for product CLI command handlers."""

    runtime: LocalAgentRuntime | None = None
    selected_context_runtime: SelectedContextLocalAgentRuntime | None = None
    script_policy_evaluator: SkillScriptPolicyEvaluator | None = None
    script_executor: SkillScriptRunner | None = None
    commit_message_workflow: CommitMessageWorkflowRunner | None = None
    confirmed_commit_workflow: ConfirmedCommitWorkflowRunner | None = None
