"""Expose live human input as the model-facing ``ask_question`` tool."""

import asyncio
import json
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolBatchPolicy,
    ToolCancellationSignal,
    ToolDefinition,
    ToolExecutionContext,
    ToolMutationGuarantee,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.user_interaction.application.dtos import (
    InteractionErrorCode,
    InteractionOwner,
    InteractionQuestion,
    InteractionResult,
)
from fabrica.features.user_interaction.application.ports import InteractionManager
from fabrica.features.user_interaction.application.use_cases import InteractionManagerError

ASK_QUESTION_TOOL_NAME = "ask_question"
INTERACTION_OWNER_CONTEXT_KEY = "user_interaction.owner"
ASK_QUESTION_TOOL_DESCRIPTION = (
    "Ask the user one focused question when progress depends materially on information or a decision\n"
    "that cannot be determined from the current conversation, workspace, or available tools.\n\n"
    "Before asking, investigate information that can be determined autonomously.\n\n"
    "Provide 2-5 concise suggested answers. Suggestions do not constrain the user's final answer;\n"
    "the user may respond with non-empty free text.\n\n"
    "Do not ask for confirmation of ordinary reversible implementation decisions. Do not use this tool for tool\n"
    "permission, destructive-action approval, or Plan-to-Execute approval."
)
ASK_QUESTION_TOOL_DEFINITION = ToolDefinition(
    name=ASK_QUESTION_TOOL_NAME,
    description=ASK_QUESTION_TOOL_DESCRIPTION,
    argument_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "minLength": 1, "maxLength": 4_000},
            "options": {
                "type": "array",
                "minItems": 2,
                "maxItems": 5,
                "items": {"type": "string", "minLength": 1, "maxLength": 500},
            },
        },
        "required": ("question", "options"),
        "additionalProperties": False,
    },
    batch_policy=ToolBatchPolicy.REQUIRE_SOLO,
)


@dataclass(frozen=True, slots=True)
class AskQuestionRegisteredToolAdapter:
    """Map model arguments and opaque owner context to the interaction boundary."""

    interaction_manager: InteractionManager

    async def handle(
        self,
        arguments: Mapping[str, ToolArgumentValue],
        context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        """Ask one question or return a structured, non-fabricated rejection."""
        try:
            question = _question_from_arguments(arguments)
        except (TypeError, ValueError) as err:
            return RegisteredToolOutcome.recoverable_rejection(
                error_code=InteractionErrorCode.INVALID_INPUT,
                error_message=str(err),
            )

        owner = context.opaque_values.get(INTERACTION_OWNER_CONTEXT_KEY)
        if not isinstance(owner, InteractionOwner):
            return RegisteredToolOutcome.recoverable_rejection(
                error_code=InteractionErrorCode.SESSION_NOT_INTERACTIVE,
                error_message="the current session does not provide an interactive user channel",
            )

        try:
            result = await _ask_until_resolved_or_cancelled(
                interaction_manager=self.interaction_manager,
                owner=owner,
                question=question,
                cancellation=context.cancellation,
            )
        except InteractionManagerError as err:
            return RegisteredToolOutcome.recoverable_rejection(error_code=err.code, error_message=str(err))
        return _result_to_outcome(result)


def create_ask_question_registered_tool(interaction_manager: InteractionManager) -> AsyncRegisteredTool:
    """Create the sole model-facing registered tool for live human interaction."""
    adapter = AskQuestionRegisteredToolAdapter(interaction_manager=interaction_manager)
    return AsyncRegisteredTool(definition=ASK_QUESTION_TOOL_DEFINITION, handler=adapter.handle)


def _question_from_arguments(arguments: Mapping[str, ToolArgumentValue]) -> InteractionQuestion:
    if set(arguments) != {"question", "options"}:
        msg = "ask_question requires exactly question and options arguments"
        raise ValueError(msg)
    question = arguments["question"]
    options = arguments["options"]
    if not isinstance(question, str):
        msg = "question must be a string"
        raise TypeError(msg)
    if not isinstance(options, tuple) or not all(isinstance(option, str) for option in options):
        msg = "options must be an array of strings"
        raise TypeError(msg)
    return InteractionQuestion(question=question, options=tuple(str(option) for option in options))


def _result_to_outcome(result: InteractionResult) -> RegisteredToolOutcome:
    payload = {
        "answer": result.answer,
        "question_id": result.question_id.value,
        "selected_option": result.selected_option,
        "status": result.status.value,
    }
    return RegisteredToolOutcome.model_continue_success(
        mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
        content=(ToolTextContent(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)),),
    )


async def _ask_until_resolved_or_cancelled(
    *,
    interaction_manager: InteractionManager,
    owner: InteractionOwner,
    question: InteractionQuestion,
    cancellation: ToolCancellationSignal,
) -> InteractionResult:
    """Resolve a question or map external runtime cancellation to cancellation."""
    ask_task = asyncio.create_task(interaction_manager.ask(owner, question))
    cancellation_task = asyncio.create_task(cancellation.wait_until_cancelled())
    try:
        done, _pending = await asyncio.wait((ask_task, cancellation_task), return_when=asyncio.FIRST_COMPLETED)
        if ask_task in done:
            return await ask_task
        await interaction_manager.cancel_owner(owner)
        return await ask_task
    finally:
        if not cancellation_task.done():
            cancellation_task.cancel()
        with suppress(asyncio.CancelledError):
            await cancellation_task
