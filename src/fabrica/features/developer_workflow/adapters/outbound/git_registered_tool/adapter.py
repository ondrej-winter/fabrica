"""Public factories for read-only git registered tools."""

from fabrica.features.agent_runtime.application.ports import RegisteredTool
from fabrica.features.developer_workflow.adapters.outbound.git_registered_tool.context_definitions import (
    GIT_BRANCH_AHEAD_BEHIND_TOOL_DEFINITION,
    GIT_COMMIT_CHANGED_FILES_TOOL_DEFINITION,
    GIT_COMMIT_DETAILS_TOOL_DEFINITION,
    GIT_COMMIT_DIFF_TOOL_DEFINITION,
    GIT_COMMIT_FILE_DIFF_TOOL_DEFINITION,
    GIT_COMMIT_LOG_TOOL_DEFINITION,
    GIT_MERGE_BASE_TOOL_DEFINITION,
    GIT_REF_CHANGED_FILES_TOOL_DEFINITION,
    GIT_REF_DIFF_TOOL_DEFINITION,
    GIT_REF_FILE_DIFF_TOOL_DEFINITION,
    GIT_STATUS_SUMMARY_TOOL_DEFINITION,
    GIT_UNSTAGED_DIFF_TOOL_DEFINITION,
    GIT_UNSTAGED_FILE_DIFF_TOOL_DEFINITION,
    GIT_UNSTAGED_FILES_TOOL_DEFINITION,
)
from fabrica.features.developer_workflow.adapters.outbound.git_registered_tool.context_handlers import (
    handle_branch_ahead_behind,
    handle_commit_changed_files,
    handle_commit_details,
    handle_commit_diff,
    handle_commit_file_diff,
    handle_commit_log,
    handle_merge_base,
    handle_ref_changed_files,
    handle_ref_diff,
    handle_ref_file_diff,
    handle_status_summary,
    handle_unstaged_diff,
    handle_unstaged_file_diff,
    handle_unstaged_files,
)
from fabrica.features.developer_workflow.adapters.outbound.git_registered_tool.staged_definitions import (
    STAGED_GIT_FILE_DIFF_TOOL_DEFINITION,
    STAGED_GIT_FILES_TOOL_DEFINITION,
    STAGED_GIT_FULL_DIFF_TOOL_DEFINITION,
)
from fabrica.features.developer_workflow.adapters.outbound.git_registered_tool.staged_handlers import (
    handle_staged_diff,
    handle_staged_file_diff,
    handle_staged_files,
)
from fabrica.features.developer_workflow.application.ports import (
    GitCommitContextLoader,
    GitRefContextLoader,
    GitStagedChangesLoader,
    GitWorktreeContextLoader,
)

__all__ = ["create_git_context_registered_tools", "create_git_staged_changes_registered_tools"]


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


def create_git_context_registered_tools(
    *,
    worktree_loader: GitWorktreeContextLoader,
    commit_loader: GitCommitContextLoader,
    ref_loader: GitRefContextLoader,
) -> tuple[RegisteredTool, ...]:
    """Create opt-in model-callable tools for explicitly supplied read-only git context loaders."""
    return (
        RegisteredTool(
            definition=GIT_STATUS_SUMMARY_TOOL_DEFINITION,
            handler=lambda arguments: handle_status_summary(worktree_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_UNSTAGED_FILES_TOOL_DEFINITION,
            handler=lambda arguments: handle_unstaged_files(worktree_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_UNSTAGED_DIFF_TOOL_DEFINITION,
            handler=lambda arguments: handle_unstaged_diff(worktree_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_UNSTAGED_FILE_DIFF_TOOL_DEFINITION,
            handler=lambda arguments: handle_unstaged_file_diff(worktree_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_COMMIT_LOG_TOOL_DEFINITION,
            handler=lambda arguments: handle_commit_log(commit_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_COMMIT_DETAILS_TOOL_DEFINITION,
            handler=lambda arguments: handle_commit_details(commit_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_COMMIT_CHANGED_FILES_TOOL_DEFINITION,
            handler=lambda arguments: handle_commit_changed_files(commit_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_COMMIT_DIFF_TOOL_DEFINITION,
            handler=lambda arguments: handle_commit_diff(commit_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_COMMIT_FILE_DIFF_TOOL_DEFINITION,
            handler=lambda arguments: handle_commit_file_diff(commit_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_REF_CHANGED_FILES_TOOL_DEFINITION,
            handler=lambda arguments: handle_ref_changed_files(ref_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_REF_DIFF_TOOL_DEFINITION,
            handler=lambda arguments: handle_ref_diff(ref_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_REF_FILE_DIFF_TOOL_DEFINITION,
            handler=lambda arguments: handle_ref_file_diff(ref_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_BRANCH_AHEAD_BEHIND_TOOL_DEFINITION,
            handler=lambda arguments: handle_branch_ahead_behind(ref_loader, arguments),
        ),
        RegisteredTool(
            definition=GIT_MERGE_BASE_TOOL_DEFINITION,
            handler=lambda arguments: handle_merge_base(ref_loader, arguments),
        ),
    )
