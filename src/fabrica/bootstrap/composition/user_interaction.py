"""Opt-in composition for live human interaction in a tool-loop run."""

from dataclasses import dataclass
from secrets import token_urlsafe

from fabrica.bootstrap.composition.tool_loop import ToolLoopRuntime
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredToolExecutor
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopRunResult,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModel
from fabrica.features.agent_runtime.application.use_cases import RunToolLoop
from fabrica.features.user_interaction.adapters.inbound.registered_tool import (
    INTERACTION_OWNER_CONTEXT_KEY,
    create_ask_question_registered_tool,
)
from fabrica.features.user_interaction.application.dtos import (
    AnswerSubmission,
    InteractionOwner,
    InteractionResult,
)
from fabrica.features.user_interaction.application.ports import InteractionManager, InteractionTransport
from fabrica.features.user_interaction.application.use_cases import InMemoryInteractionManager


@dataclass(frozen=True, slots=True)
class InteractiveToolLoopRun:
    """One host-owned interactive run with an opaque answer authorization token."""

    _runtime: ToolLoopRuntime
    _interaction_manager: InteractionManager
    owner: InteractionOwner

    async def run(
        self,
        command: LocalAgentRunCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolLoopRunResult:
        """Run until completion, cancelling and releasing this owner's interactions."""
        try:
            return await self._runtime.run(
                command,
                cancellation=cancellation,
                opaque_tool_context={INTERACTION_OWNER_CONTEXT_KEY: self.owner},
            )
        finally:
            await self._interaction_manager.release_owner(self.owner)

    async def submit_answer(self, submission: AnswerSubmission) -> InteractionResult:
        """Submit a structured answer authorized for this run only."""
        return await self._interaction_manager.submit_answer(self.owner, submission)

    async def cancel_question(self, question_id: str) -> InteractionResult:
        """Cancel one question authorized for this run only."""
        return await self._interaction_manager.cancel(self.owner, question_id)

    async def cancel(self) -> None:
        """Cancel every pending interaction for this run."""
        await self._interaction_manager.cancel_owner(self.owner)


@dataclass(frozen=True, slots=True)
class InteractiveToolLoopRuntime:
    """Host-facing opt-in runtime that makes ``ask_question`` available."""

    _runtime: ToolLoopRuntime
    _interaction_manager: InteractionManager

    @property
    def available_tools(self) -> tuple[ToolDefinition, ...]:
        """Return the model-callable definitions, including ``ask_question``."""
        return self._runtime.available_tools

    def start_run(self) -> InteractiveToolLoopRun:
        """Create a new independently authorized interactive run."""
        return InteractiveToolLoopRun(
            _runtime=self._runtime,
            _interaction_manager=self._interaction_manager,
            owner=InteractionOwner(f"interaction_{token_urlsafe(24)}"),
        )

    async def run(
        self,
        command: LocalAgentRunCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolLoopRunResult:
        """Create one opaque owner and run without exposing it to the model."""
        return await self.start_run().run(command, cancellation=cancellation)


def create_interactive_tool_loop_runtime(
    *,
    model: ToolAwareAgentModel,
    transport: InteractionTransport,
) -> InteractiveToolLoopRuntime:
    """Create an opt-in interactive runtime from explicit model and host transport."""
    manager = InMemoryInteractionManager(transport)
    executor = RegisteredToolExecutor((create_ask_question_registered_tool(manager),))
    return InteractiveToolLoopRuntime(
        _runtime=ToolLoopRuntime(
            runner=RunToolLoop(model=model, tool_executor=executor),
            available_tools=executor.tool_definitions,
        ),
        _interaction_manager=manager,
    )
