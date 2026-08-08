"""Prompt and message rendering helpers for PydanticAI runtime adapters."""

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

from fabrica.features.agent_runtime.application.dtos import LocalAgentContextBlock, LocalAgentRunCommand


def build_user_prompt(command: LocalAgentRunCommand) -> str:
    """Render a local agent command into the bounded user prompt text."""
    if not command.context:
        return command.prompt

    context_text = "\n\n".join(_format_context_block(block) for block in command.context)
    return f"Context:\n{context_text}\n\nPrompt:\n{command.prompt}"


def render_message(message: ModelMessage) -> str:
    """Serialize a PydanticAI model message for adapter-local diagnostics."""
    return ModelMessagesTypeAdapter.dump_json([message]).decode("utf-8")


def _format_context_block(block: LocalAgentContextBlock) -> str:
    if block.label is None:
        return block.text
    return f"[{block.label}]\n{block.text}"
