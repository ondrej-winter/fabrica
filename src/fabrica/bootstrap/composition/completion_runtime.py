"""Host-facing opaque run ownership for terminal completion compositions."""

from dataclasses import dataclass
from uuid import uuid4

from fabrica.bootstrap.composition.tool_loop import ToolLoopRuntime
from fabrica.features.agent_runtime.application.dtos import (
    RUN_ID_CONTEXT_KEY,
    CompletionRecord,
    LocalAgentRunCommand,
    ToolCancellationSignal,
    ToolLoopRunResult,
)
from fabrica.features.agent_runtime.application.ports import CompletionPresenter, CompletionStore


@dataclass(frozen=True, slots=True)
class CompletionToolLoopRun:
    """One host-owned tool-loop run with an opaque completion-store identifier."""

    _runtime: ToolLoopRuntime
    run_id: str
    _completion_store: CompletionStore | None = None
    _completion_presenter: CompletionPresenter | None = None

    async def run(
        self,
        command: LocalAgentRunCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolLoopRunResult:
        """Run with the opaque identifier available only to registered tools."""
        result = await self._runtime.run(
            command,
            cancellation=cancellation,
            opaque_tool_context={RUN_ID_CONTEXT_KEY: self.run_id},
        )
        await self._present_committed_completion()
        return result

    async def _present_committed_completion(self) -> None:
        if self._completion_store is None or self._completion_presenter is None:
            return
        records = await self._completion_store.list_unpresented()
        for record in records:
            if record.run_id == self.run_id:
                await _present_and_acknowledge(record, self._completion_store, self._completion_presenter)
                return


@dataclass(frozen=True, slots=True)
class CompletionToolLoopRuntime:
    """Host-facing factory for independently identified terminal-completion runs."""

    runtime: ToolLoopRuntime
    completion_store: CompletionStore | None = None
    completion_presenter: CompletionPresenter | None = None

    def start_run(self) -> CompletionToolLoopRun:
        """Create a fresh opaque run identifier without exposing it to the model."""
        return CompletionToolLoopRun(
            _runtime=self.runtime,
            run_id=f"run_{uuid4()}",
            _completion_store=self.completion_store,
            _completion_presenter=self.completion_presenter,
        )

    async def recover_unpresented_completions(self) -> tuple[CompletionRecord, ...]:
        """Present every durably committed completion not yet acknowledged by the host."""
        if self.completion_store is None or self.completion_presenter is None:
            return ()
        records = await self.completion_store.list_unpresented()
        for record in records:
            await _present_and_acknowledge(record, self.completion_store, self.completion_presenter)
        return records


async def _present_and_acknowledge(
    record: CompletionRecord,
    completion_store: CompletionStore,
    completion_presenter: CompletionPresenter,
) -> None:
    """Render a canonical completion record before recording durable acknowledgement."""
    await completion_presenter.present(record)
    await completion_store.acknowledge_presented(record.run_id)


__all__ = ["CompletionToolLoopRun", "CompletionToolLoopRuntime"]
