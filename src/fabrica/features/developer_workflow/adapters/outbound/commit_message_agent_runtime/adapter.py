"""Agent-runtime-backed outbound adapters for commit-message generation."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand, LocalAgentRunResult
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime.mappers import (
    parse_analysis_output,
    parse_synthesis_output,
    safe_runtime_metadata,
    to_analysis_runtime_command,
    to_synthesis_runtime_command,
)
from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageRecommendation,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageAnalysisError,
    CommitMessageSynthesisError,
)


class CommitMessageAgentRuntime(Protocol):
    """Runtime protocol required by commit-message agent-runtime adapters."""

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command."""
        ...

    async def run_async(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command asynchronously."""
        ...


class AgentRuntimeStagedFileCommitMessageAnalyzer:
    """Analyze one staged file through an injected local agent runtime."""

    def __init__(self, runtime: CommitMessageAgentRuntime) -> None:
        self._runtime = runtime

    def analyze(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        """Return structured evidence parsed from one agent-runtime response."""
        runtime_result = self._runtime.run(to_analysis_runtime_command(command))
        return _parse_analysis_runtime_result(runtime_result, command)

    async def analyze_async(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        """Return structured evidence parsed from one async agent-runtime response."""
        runtime_result = await self._runtime.run_async(to_analysis_runtime_command(command))
        return _parse_analysis_runtime_result(runtime_result, command)


def _parse_analysis_runtime_result(
    runtime_result: LocalAgentRunResult,
    command: AnalyzeStagedFileForCommitMessageCommand,
) -> StagedFileCommitEvidence:
    """Parse one analysis runtime result into application evidence."""
    if not runtime_result.succeeded or runtime_result.output_text is None:
        msg = "commit-message analysis runtime failed"
        raise CommitMessageAnalysisError(
            msg,
            metadata={
                "path": command.staged_file.path,
                **safe_runtime_metadata(runtime_result.status.value, runtime_result.output_text),
            },
        )
    return parse_analysis_output(runtime_result.output_text, command)


class AgentRuntimeCommitMessageSynthesizer:
    """Synthesize a final recommendation through an injected local agent runtime."""

    def __init__(self, runtime: CommitMessageAgentRuntime) -> None:
        self._runtime = runtime

    def synthesize(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        """Return a parsed recommendation from one final agent-runtime response."""
        runtime_result = self._runtime.run(to_synthesis_runtime_command(command))
        return _parse_synthesis_runtime_result(runtime_result)

    async def synthesize_async(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        """Return a parsed recommendation from one async final agent-runtime response."""
        runtime_result = await self._runtime.run_async(to_synthesis_runtime_command(command))
        return _parse_synthesis_runtime_result(runtime_result)


def _parse_synthesis_runtime_result(runtime_result: LocalAgentRunResult) -> CommitMessageRecommendation:
    """Parse one synthesis runtime result into an application recommendation."""
    if not runtime_result.succeeded or runtime_result.output_text is None:
        msg = "commit-message synthesis runtime failed"
        raise CommitMessageSynthesisError(
            msg,
            metadata=safe_runtime_metadata(runtime_result.status.value, runtime_result.output_text),
        )
    return parse_synthesis_output(runtime_result.output_text)
