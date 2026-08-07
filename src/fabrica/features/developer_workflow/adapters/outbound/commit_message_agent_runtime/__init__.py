"""Agent-runtime-backed commit-message analysis and synthesis adapters."""

from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime.analysis import (
    AgentRuntimeStagedFileCommitMessageAnalyzer,
)
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime.synthesis import (
    AgentRuntimeCommitMessageSynthesizer,
)

__all__ = [
    "AgentRuntimeCommitMessageSynthesizer",
    "AgentRuntimeStagedFileCommitMessageAnalyzer",
]
