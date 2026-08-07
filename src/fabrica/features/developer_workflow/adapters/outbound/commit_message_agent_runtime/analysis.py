"""Agent-runtime-backed staged-file commit-message analyzer."""

from fabrica.features.agent_runtime.application.dtos import LocalAgentRunResult
from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    StagedFileCommitEvidence,
)
from fabrica.features.developer_workflow.application.ports import CommitMessageAnalysisError

from .analysis_mapping import to_analysis_runtime_command
from .analysis_parsing import parse_analysis_output
from .metadata import safe_runtime_metadata
from .runtime import CommitMessageAgentRuntime


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
