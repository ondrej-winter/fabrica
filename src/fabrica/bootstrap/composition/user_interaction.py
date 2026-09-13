"""Opt-in composition for live human interaction in a tool-loop run."""

from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from secrets import token_urlsafe

from fabrica.bootstrap.composition.tool_loop import ToolLoopRuntime
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import (
    AsyncRegisteredTool,
    RegisteredTool,
    RegisteredToolExecutor,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunResult,
)
from fabrica.features.agent_runtime.application.ports import (
    ToolAwareAgentModel,
    ToolAwareAgentModelError,
    ToolExecutionError,
    ToolExecutor,
)
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

_ACTIVE_INTERACTIVE_RUN: ContextVar[InteractiveToolLoopRun | None] = ContextVar("active_interactive_run", default=None)
type ModelResponseObserver = Callable[[ToolAwareModelResponse], None]
type ToolResultObserver = Callable[[ToolCallResult], None]


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
        """Run until completion with this run's opaque interaction authorization."""
        token = _ACTIVE_INTERACTIVE_RUN.set(self)
        try:
            return await self._runtime.run(
                command,
                cancellation=cancellation,
                opaque_tool_context={INTERACTION_OWNER_CONTEXT_KEY: self.owner},
            )
        finally:
            _ACTIVE_INTERACTIVE_RUN.reset(token)

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
    tools: tuple[RegisteredTool | AsyncRegisteredTool, ...] = (),
    model_response_observer: ModelResponseObserver | None = None,
    tool_result_observer: ToolResultObserver | None = None,
) -> InteractiveToolLoopRuntime:
    """Create an interactive runtime from explicit tools, model, and host transport.

    The runtime always exposes its host-owned ``ask_question`` tool in addition
    to the supplied registrations. Duplicate tool names, including a supplied
    ``ask_question`` registration, fail during construction.
    """
    manager = InMemoryInteractionManager(transport)
    registered_executor = RegisteredToolExecutor((*tools, create_ask_question_registered_tool(manager)))
    executor = _ObservedToolExecutor(registered_executor, tool_result_observer)

    async def release_interaction_owner(opaque_context: Mapping[str, object]) -> None:
        owner = opaque_context.get(INTERACTION_OWNER_CONTEXT_KEY)
        if isinstance(owner, InteractionOwner):
            await manager.release_owner(owner)

    return InteractiveToolLoopRuntime(
        _runtime=ToolLoopRuntime(
            runner=RunToolLoop(
                model=_ObservedToolAwareAgentModel(model, model_response_observer),
                tool_executor=executor,
                terminal_hooks=(release_interaction_owner,),
            ),
            available_tools=registered_executor.tool_definitions,
        ),
        _interaction_manager=manager,
    )


def active_interactive_run() -> InteractiveToolLoopRun:
    """Return the host-owned interactive run currently publishing a question."""
    run = _ACTIVE_INTERACTIVE_RUN.get()
    if run is None:
        msg = "no interactive run is active"
        raise RuntimeError(msg)
    return run


@dataclass(frozen=True, slots=True)
class _ObservedToolAwareAgentModel:
    """Record completed normalized model turns before returning them to the loop."""

    delegate: ToolAwareAgentModel
    observer: ModelResponseObserver | None

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        """Delegate one turn and synchronously publish its normalized completion."""
        response = await self.delegate.run_turn(command, available_tools, tool_results, cancellation)
        if self.observer is not None:
            try:
                self.observer(response)
            except RuntimeError as err:
                msg = "durable session model recording failed"
                raise ToolAwareAgentModelError(msg, category="durable_session_recording") from err
        return response


@dataclass(frozen=True, slots=True)
class _ObservedToolExecutor:
    """Record completed normalized tool outcomes before returning them to the loop."""

    delegate: ToolExecutor
    observer: ToolResultObserver | None

    async def execute_tool(
        self,
        request: ToolCallRequest,
        limits: ToolLoopLimits,
        cancellation: ToolCancellationSignal,
        opaque_context: Mapping[str, object] | None = None,
    ) -> ToolCallResult:
        """Delegate one tool and convert observation persistence failure to an adapter failure."""
        result = await self.delegate.execute_tool(request, limits, cancellation, opaque_context)
        if self.observer is None:
            return result
        try:
            self.observer(result)
        except RuntimeError as err:
            msg = "durable session tool recording failed"
            raise ToolExecutionError(msg, category="durable_session_recording") from err
        return result
