"""Public factory for the pre-commit registered tool."""

from fabrica.features.agent_runtime.application.ports import RegisteredTool
from fabrica.features.developer_workflow.adapters.outbound.pre_commit_registered_tool.definitions import (
    RUN_PRE_COMMIT_TOOL_DEFINITION,
)
from fabrica.features.developer_workflow.adapters.outbound.pre_commit_registered_tool.handlers import (
    handle_run_pre_commit,
)
from fabrica.features.developer_workflow.application.ports import PreCommitRunner

__all__ = ["create_pre_commit_registered_tools"]


def create_pre_commit_registered_tools(runner: PreCommitRunner) -> tuple[RegisteredTool, ...]:
    """Create explicitly opt-in model-callable tools for pre-commit execution."""
    return (
        RegisteredTool(
            definition=RUN_PRE_COMMIT_TOOL_DEFINITION,
            handler=lambda arguments: handle_run_pre_commit(runner, arguments),
        ),
    )
