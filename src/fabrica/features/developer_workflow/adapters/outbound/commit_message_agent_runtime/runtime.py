"""Runtime protocol for commit-message agent-runtime adapters."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand, LocalAgentRunResult


class CommitMessageAgentRuntime(Protocol):
    """Runtime protocol required by commit-message agent-runtime adapters."""

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command."""
        ...

    async def run_async(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command asynchronously."""
        ...
