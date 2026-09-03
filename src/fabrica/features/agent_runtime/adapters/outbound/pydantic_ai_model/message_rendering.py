"""Prompt and message rendering helpers for PydanticAI runtime adapters."""

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

from fabrica.features.agent_runtime.application.dtos import LocalAgentContextBlock, LocalAgentRunCommand


def build_user_prompt(command: LocalAgentRunCommand) -> str:
    """Render a local agent command into the bounded user prompt text."""
    if not command.context and not command.instructions:
        return command.prompt
    sections: list[str] = []
    if command.context:
        context = "\n\n".join(_format_context_block(block) for block in command.context)
        sections.append(f"Context:\n{context}")
    if command.instructions:
        instructions = "\n\n".join(
            f"[{instruction.instruction_type}]\n{instruction.text}" for instruction in command.instructions
        )
        sections.append(f"Instructions:\n{instructions}")
    sections.append(f"Prompt:\n{command.prompt}")
    return "\n\n".join(sections)


def render_message(message: ModelMessage) -> str:
    """Serialize a PydanticAI model message for adapter-local diagnostics."""
    return ModelMessagesTypeAdapter.dump_json([message]).decode("utf-8")


def _format_context_block(block: LocalAgentContextBlock) -> str:
    if block.label is None:
        return block.text
    return f"[{block.label}]\n{block.text}"
