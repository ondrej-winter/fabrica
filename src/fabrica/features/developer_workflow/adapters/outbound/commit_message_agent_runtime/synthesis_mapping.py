"""Mapping from commit-message synthesis commands to local agent runtime commands."""

from fabrica.features.agent_runtime.application.dtos import LocalAgentContextBlock, LocalAgentRunCommand
from fabrica.features.developer_workflow.application.dtos import SynthesizeCommitMessageCommand

from .synthesis_prompt import SYNTHESIZE_COMMIT_MESSAGE_PROMPT


def to_synthesis_runtime_command(command: SynthesizeCommitMessageCommand) -> LocalAgentRunCommand:
    """Map final synthesis input to a local agent runtime command."""
    context = [
        LocalAgentContextBlock(
            text=command.evidence_bundle.serialized_text,
            label="Commit-message structured evidence",
            metadata={
                "source": "commit_message_evidence",
                "evidence_count": len(command.evidence_bundle.evidence),
                "char_count": len(command.evidence_bundle.serialized_text),
            },
        ),
    ]
    if command.skill_markdown is not None:
        context.append(
            LocalAgentContextBlock(
                text=command.skill_markdown,
                label=f"Agent Skill: {command.skill_id}",
                metadata={"source": "agent_skill", "skill_id": command.skill_id},
            ),
        )
    return LocalAgentRunCommand(prompt=SYNTHESIZE_COMMIT_MESSAGE_PROMPT, context=tuple(context))
