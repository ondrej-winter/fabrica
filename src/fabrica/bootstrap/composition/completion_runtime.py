"""Host-facing opaque run ownership for terminal completion compositions."""

from dataclasses import dataclass
from uuid import uuid4

from fabrica.bootstrap.composition.tool_loop import ToolLoopRuntime
from fabrica.features.agent_runtime.application.dtos import (
    RUN_ID_CONTEXT_KEY,
    LocalAgentRunCommand,
    ToolCancellationSignal,
    ToolLoopRunResult,
)


@dataclass(frozen=True, slots=True)
class CompletionToolLoopRun:
    """One host-owned tool-loop run with an opaque completion-store identifier."""

    _runtime: ToolLoopRuntime
    run_id: str

    async def run(
        self,
        command: LocalAgentRunCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolLoopRunResult:
        """Run with the opaque identifier available only to registered tools."""
        return await self._runtime.run(
            command,
            cancellation=cancellation,
            opaque_tool_context={RUN_ID_CONTEXT_KEY: self.run_id},
        )


@dataclass(frozen=True, slots=True)
class CompletionToolLoopRuntime:
    """Host-facing factory for independently identified terminal-completion runs."""

    runtime: ToolLoopRuntime

    def start_run(self) -> CompletionToolLoopRun:
        """Create a fresh opaque run identifier without exposing it to the model."""
        return CompletionToolLoopRun(_runtime=self.runtime, run_id=f"run_{uuid4()}")


__all__ = ["CompletionToolLoopRun", "CompletionToolLoopRuntime"]
