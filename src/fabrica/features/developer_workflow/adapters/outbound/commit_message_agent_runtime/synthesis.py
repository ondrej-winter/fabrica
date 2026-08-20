"""Agent-runtime-backed commit-message synthesizer."""

from fabrica.features.agent_runtime.application.dtos import LocalAgentRunResult
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    DeveloperWorkflowStatus,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import CommitMessageSynthesisError

from .metadata import safe_runtime_metadata
from .runtime import CommitMessageAgentRuntime
from .synthesis_mapping import to_synthesis_runtime_command
from .synthesis_parsing import parse_synthesis_output


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
            status=_developer_workflow_status_from_runtime(runtime_result.status),
            metadata=safe_runtime_metadata(
                runtime_result.status.value,
                runtime_result.output_text,
                runtime_result.observations,
            ),
        )
    return parse_synthesis_output(runtime_result.output_text)


def _developer_workflow_status_from_runtime(status: object) -> DeveloperWorkflowStatus:
    runtime_status = getattr(status, "value", status)
    if runtime_status == "configuration_error":
        return DeveloperWorkflowStatus.CONFIGURATION_ERROR
    return DeveloperWorkflowStatus.MODEL_ERROR
