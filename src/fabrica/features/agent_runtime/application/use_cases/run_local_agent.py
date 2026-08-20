"""Use case for running one local agent command."""

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    RuntimeObservation,
)
from fabrica.features.agent_runtime.application.ports import AgentModel, AgentModelError


class RunLocalAgent:
    """Orchestrate one local agent run through an injected model port."""

    def __init__(self, model: AgentModel) -> None:
        self._model = model

    async def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command and normalize model dependency failures."""
        try:
            return await self._model.run(command)
        except AgentModelError as err:
            return LocalAgentRunResult(
                status=err.status,
                observations=(
                    RuntimeObservation(
                        message="model dependency failed",
                        metadata={"error_type": type(err).__name__, **err.metadata},
                    ),
                ),
            )
