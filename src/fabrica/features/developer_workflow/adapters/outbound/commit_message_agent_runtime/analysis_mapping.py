"""Mapping from staged-file analysis commands to local agent runtime commands."""

from fabrica.features.agent_runtime.application.dtos import LocalAgentContextBlock, LocalAgentRunCommand
from fabrica.features.developer_workflow.application.dtos import AnalyzeStagedFileForCommitMessageCommand

from .analysis_prompt import ANALYZE_STAGED_FILE_PROMPT


def to_analysis_runtime_command(command: AnalyzeStagedFileForCommitMessageCommand) -> LocalAgentRunCommand:
    """Map one staged-file analysis command to one local agent runtime command."""
    return LocalAgentRunCommand(
        prompt=ANALYZE_STAGED_FILE_PROMPT,
        context=(
            LocalAgentContextBlock(
                text=command.diff.text,
                label=f"Staged file diff: {command.staged_file.path}",
                metadata={
                    "source": "git_staged_file_diff",
                    "path": command.staged_file.path,
                    "status": command.staged_file.status.value,
                    "char_count": len(command.diff.text),
                    **command.diff.metadata,
                },
            ),
        ),
    )
