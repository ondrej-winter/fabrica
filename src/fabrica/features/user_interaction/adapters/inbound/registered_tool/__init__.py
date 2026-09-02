"""Model-facing registered-tool adapter for live user interaction."""

from fabrica.features.user_interaction.adapters.inbound.registered_tool.adapter import (
    ASK_QUESTION_TOOL_DEFINITION,
    ASK_QUESTION_TOOL_DESCRIPTION,
    ASK_QUESTION_TOOL_NAME,
    INTERACTION_OWNER_CONTEXT_KEY,
    AskQuestionRegisteredToolAdapter,
    create_ask_question_registered_tool,
)

__all__ = [
    "ASK_QUESTION_TOOL_DEFINITION",
    "ASK_QUESTION_TOOL_DESCRIPTION",
    "ASK_QUESTION_TOOL_NAME",
    "INTERACTION_OWNER_CONTEXT_KEY",
    "AskQuestionRegisteredToolAdapter",
    "create_ask_question_registered_tool",
]
