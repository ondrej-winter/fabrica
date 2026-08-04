"""Public interface for staged git registered tools."""

from fabrica.features.agent_runtime.application.ports import RegisteredTool
from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_registered_tool.definitions import (
    STAGED_GIT_FILE_DIFF_TOOL_DEFINITION,
    STAGED_GIT_FILES_TOOL_DEFINITION,
    STAGED_GIT_FULL_DIFF_TOOL_DEFINITION,
)
from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_registered_tool.handlers import (
    handle_staged_diff,
    handle_staged_file_diff,
    handle_staged_files,
)
from fabrica.features.developer_workflow.application.ports import (
    GitStagedChangesLoader,
)

__all__ = ["create_git_staged_changes_registered_tools"]


def create_git_staged_changes_registered_tools(loader: GitStagedChangesLoader) -> tuple[RegisteredTool, ...]:
    """Create model-callable tools for explicitly supplied staged git loading."""
    return (
        RegisteredTool(
            definition=STAGED_GIT_FILES_TOOL_DEFINITION,
            handler=lambda arguments: handle_staged_files(loader, arguments),
        ),
        RegisteredTool(
            definition=STAGED_GIT_FULL_DIFF_TOOL_DEFINITION,
            handler=lambda arguments: handle_staged_diff(loader, arguments),
        ),
        RegisteredTool(
            definition=STAGED_GIT_FILE_DIFF_TOOL_DEFINITION,
            handler=lambda arguments: handle_staged_file_diff(loader, arguments),
        ),
    )
