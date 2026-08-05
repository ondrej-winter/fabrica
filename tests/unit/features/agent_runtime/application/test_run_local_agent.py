"""Tests for local agent runtime orchestration."""

from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
)
from fabrica.features.agent_runtime.application.ports import AgentModelError
from fabrica.features.agent_runtime.application.use_cases import RunLocalAgent


@dataclass
class FakeAgentModel:
    result: LocalAgentRunResult | None = None
    error: AgentModelError | None = None
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        if self.error is not None:
            raise self.error
        if self.result is None:
            msg = "test fake requires a result or error"
            raise AssertionError(msg)
        return self.result

    async def run_async(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        return self.run(command)


def test_run_local_agent_delegates_to_model_port() -> None:
    command = LocalAgentRunCommand(prompt="Reply with the single word: pong")
    model_result = LocalAgentRunResult(
        status=LocalAgentRunStatus.SUCCESS,
        output_text="pong",
        observations=(RuntimeObservation(message="fake model completed"),),
    )
    model = FakeAgentModel(result=model_result)

    result = RunLocalAgent(model=model).run(command)

    assert result == model_result
    assert model.calls == [command]


def test_run_local_agent_normalizes_model_port_failures() -> None:
    command = LocalAgentRunCommand(prompt="Reply with the single word: pong")
    model = FakeAgentModel(
        error=AgentModelError(
            "synthetic model unavailable",
            status=LocalAgentRunStatus.CONFIGURATION_ERROR,
            metadata={"category": "missing_configuration"},
        ),
    )

    result = RunLocalAgent(model=model).run(command)

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
    assert result.succeeded is False
    assert result.output_text is None
    assert result.observations == (
        RuntimeObservation(
            message="model dependency failed",
            metadata={"error_type": "AgentModelError", "category": "missing_configuration"},
        ),
    )
    assert model.calls == [command]
