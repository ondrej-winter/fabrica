"""Agent-runtime-backed commit-message analysis and synthesis adapters."""

from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime.adapter import (
    AgentRuntimeCommitMessageSynthesizer,
    AgentRuntimeStagedFileCommitMessageAnalyzer,
)

__all__ = [
    "AgentRuntimeCommitMessageSynthesizer",
    "AgentRuntimeStagedFileCommitMessageAnalyzer",
]
