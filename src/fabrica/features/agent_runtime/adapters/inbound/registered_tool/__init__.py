"""Model-facing registered tools owned by the agent-runtime slice."""

from fabrica.features.agent_runtime.adapters.inbound.registered_tool.submit_and_exit import (
    SubmitAndExitRegisteredToolAdapter,
    create_submit_and_exit_registered_tool,
)

__all__ = ["SubmitAndExitRegisteredToolAdapter", "create_submit_and_exit_registered_tool"]
