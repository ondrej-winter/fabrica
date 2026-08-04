"""Runtime model adapter backed by PydanticAI custom model support."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior, UserError
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelResponse, TextPart
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
    SafeRuntimeMetadataValue,
)


@dataclass(frozen=True, slots=True)
class PydanticAICompletionRequest:
    """Adapter-local completion request rendered from PydanticAI messages."""

    prompt: str
    model_hint: str | None
    messages: tuple[str, ...]


class PydanticAICompletionError(Exception):
    """Runtime-safe synthetic completion dependency error."""

    def __init__(
        self,
        message: str,
        *,
        status: LocalAgentRunStatus = LocalAgentRunStatus.MODEL_ERROR,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.metadata = dict(metadata or {})


class PydanticAICompletion(Protocol):
    """Adapter-local dependency used by the custom PydanticAI model proof."""

    def complete(self, request: PydanticAICompletionRequest) -> str:
        """Return text for one rendered PydanticAI request."""
        ...


class PydanticAIAgentModel:
    """Adapt PydanticAI agent execution to the local runtime model port."""

    def __init__(self, completion: PydanticAICompletion, *, model_name: str = "synthetic-codex") -> None:
        self._completion = completion
        self._model_name = model_name

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command through an adapter-local PydanticAI agent."""
        model = _CompletionModel(
            completion=self._completion,
            source_command=command,
            model_name=command.model_hint or self._model_name,
        )
        agent: Agent[None, str] = Agent(model=model, output_type=str, tools=())

        try:
            result = agent.run_sync(_build_user_prompt(command))
        except PydanticAICompletionError as err:
            return _failure_result(err.status, "pydanticai completion failed", err.metadata)
        except UserError as err:
            return _failure_result(
                LocalAgentRunStatus.UNSUPPORTED_CAPABILITY,
                "pydanticai unsupported capability",
                {"error_type": type(err).__name__},
            )
        except UnexpectedModelBehavior as err:
            return _failure_result(
                LocalAgentRunStatus.MODEL_ERROR,
                "pydanticai model behavior failed",
                {"error_type": type(err).__name__},
            )

        return LocalAgentRunResult(
            status=LocalAgentRunStatus.SUCCESS,
            output_text=result.output,
            observations=(
                RuntimeObservation(
                    message="pydanticai completion succeeded",
                    metadata={"model_name": model.model_name, "pydantic_ai_model_system": model.system},
                ),
            ),
        )


class _CompletionModel(Model[None]):
    """Minimal custom PydanticAI model that delegates text generation to a local dependency."""

    def __init__(
        self,
        *,
        completion: PydanticAICompletion,
        source_command: LocalAgentRunCommand,
        model_name: str,
    ) -> None:
        super().__init__()
        self._completion = completion
        self._source_command = source_command
        self._model_name = model_name

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Return a PydanticAI text response from the adapter-local completion dependency."""
        _ = (model_settings, model_request_parameters)
        prepared_messages = self.prepare_messages(messages)
        output_text = self._completion.complete(
            PydanticAICompletionRequest(
                prompt=_build_user_prompt(self._source_command),
                model_hint=self._source_command.model_hint,
                messages=tuple(_render_message(message) for message in prepared_messages),
            ),
        )
        return ModelResponse(parts=[TextPart(output_text)], model_name=self.model_name)

    @property
    def model_name(self) -> str:
        """Return the synthetic model name exposed to PydanticAI internals."""
        return self._model_name

    @property
    def system(self) -> str:
        """Return the adapter-local provider identifier for telemetry-safe metadata."""
        return "fabrica-pydanticai"


def _build_user_prompt(command: LocalAgentRunCommand) -> str:
    if not command.context:
        return command.prompt

    context_text = "\n\n".join(_format_context_block(block) for block in command.context)
    return f"Context:\n{context_text}\n\nPrompt:\n{command.prompt}"


def _format_context_block(block: LocalAgentContextBlock) -> str:
    if block.label is None:
        return block.text
    return f"[{block.label}]\n{block.text}"


def _render_message(message: ModelMessage) -> str:
    return ModelMessagesTypeAdapter.dump_json([message]).decode("utf-8")


def _failure_result(
    status: LocalAgentRunStatus,
    message: str,
    metadata: Mapping[str, SafeRuntimeMetadataValue],
) -> LocalAgentRunResult:
    return LocalAgentRunResult(
        status=status,
        observations=(
            RuntimeObservation(
                message=message,
                metadata={"adapter": "pydantic_ai_model", **metadata},
            ),
        ),
    )
