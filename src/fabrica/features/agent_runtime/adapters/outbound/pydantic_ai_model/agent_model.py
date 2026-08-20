"""Runtime model adapter backed by PydanticAI custom model support."""

import asyncio

from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior, UserError

from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model.completion import (
    PydanticAICompletion,
    PydanticAICompletionError,
)
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model.message_rendering import build_user_prompt
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model.pydantic_model import CompletionModel
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model.result_mapping import failure_result
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
)


class PydanticAIAgentModel:
    """Adapt PydanticAI agent execution to the local runtime model port."""

    def __init__(self, completion: PydanticAICompletion, *, model_name: str = "synthetic-codex") -> None:
        self._completion = completion
        self._model_name = model_name

    async def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command through an adapter-local PydanticAI agent without blocking the event loop."""
        return await asyncio.to_thread(self._run_blocking, command)

    def _run_blocking(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command through the synchronous PydanticAI API."""
        model = CompletionModel(
            completion=self._completion,
            source_command=command,
            model_name=command.model_hint or self._model_name,
        )
        agent: Agent[None, str] = Agent(model=model, output_type=str, tools=())

        try:
            result = agent.run_sync(build_user_prompt(command))
        except PydanticAICompletionError as err:
            return failure_result(err.status, "pydanticai completion failed", err.metadata)
        except UserError as err:
            return failure_result(
                LocalAgentRunStatus.UNSUPPORTED_CAPABILITY,
                "pydanticai unsupported capability",
                {"error_type": type(err).__name__},
            )
        except UnexpectedModelBehavior as err:
            return failure_result(
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
