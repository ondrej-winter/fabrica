"""Custom PydanticAI model implementation backed by a local completion dependency."""

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings

from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model.completion import (
    PydanticAICompletion,
    PydanticAICompletionRequest,
)
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model.message_rendering import (
    build_user_prompt,
    render_message,
)
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand


class CompletionModel(Model[None]):
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
                prompt=build_user_prompt(self._source_command),
                model_hint=self._source_command.model_hint,
                messages=tuple(render_message(message) for message in prepared_messages),
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
