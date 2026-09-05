"""Public composition-root API for Fabrica."""

from fabrica.bootstrap.composition.codex_runtime import (
    DEFAULT_CODEX_AUTH_FILE,
    DEFAULT_COMMIT_MESSAGE_CODEX_MODEL,
    DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT,
    create_codex_pydantic_ai_runtime,
    create_codex_runtime,
    create_pydantic_ai_runtime,
)
from fabrica.bootstrap.composition.developer_workflow import (
    CommitMessageWorkflowOptions,
    PreCommitToolOptions,
    StagedGitToolOptions,
    create_codex_commit_message_workflow,
    create_codex_confirmed_commit_workflow,
    create_commit_message_workflow,
    create_confirmed_commit_workflow,
    create_pre_commit_registered_tool_adapters,
    create_staged_git_registered_tools,
)
from fabrica.bootstrap.composition.skill_context import (
    SkillContextAugmentationOptions,
    create_skill_augmented_local_agent_command,
    create_skill_context_augmented_local_agent_command,
    create_skill_context_loader,
    create_skill_resource_augmented_local_agent_command,
    create_skill_resource_context_loader,
)
from fabrica.bootstrap.composition.skill_scripts import (
    DenyByDefaultSkillScriptApprovalLookup,
    SkillScriptExecutionOptions,
    SkillScriptPolicyEvaluationOptions,
    create_skill_script_executor,
    create_skill_script_policy_evaluator,
)
from fabrica.bootstrap.composition.tool_loop import (
    ActiveSkillCompactionOptions,
    ModelDrivenSkillRuntime,
    ModelDrivenSkillRuntimeOptions,
    ToolLoopRuntime,
    create_model_driven_skill_runtime,
    create_pydantic_ai_model_driven_skill_runtime,
    create_pydantic_ai_tool_loop_runtime,
    create_tool_loop_runtime,
)
from fabrica.bootstrap.composition.user_interaction import (
    InteractiveToolLoopRun,
    InteractiveToolLoopRuntime,
    create_interactive_tool_loop_runtime,
)
from fabrica.bootstrap.composition.web_content_fetching import (
    FetchWebContentToolOptions,
    create_fetch_web_content_registered_tool_adapter,
)
from fabrica.bootstrap.composition.workspace_command_execution import (
    RunCommandsToolOptions,
    create_run_commands_registered_tool_adapter,
)
from fabrica.bootstrap.composition.workspace_editing import (
    ProductionWorkspaceEditingComposition,
    ProductionWorkspaceEditingOptions,
    create_apply_patch_registered_tool_adapter,
    create_production_workspace_editing_composition,
)
from fabrica.bootstrap.composition.workspace_reading import create_read_files_registered_tool_adapter
from fabrica.bootstrap.composition.workspace_searching import create_search_codebase_registered_tool_adapter

__all__ = [
    "DEFAULT_CODEX_AUTH_FILE",
    "DEFAULT_COMMIT_MESSAGE_CODEX_MODEL",
    "DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT",
    "ActiveSkillCompactionOptions",
    "CommitMessageWorkflowOptions",
    "DenyByDefaultSkillScriptApprovalLookup",
    "FetchWebContentToolOptions",
    "InteractiveToolLoopRun",
    "InteractiveToolLoopRuntime",
    "ModelDrivenSkillRuntime",
    "ModelDrivenSkillRuntimeOptions",
    "PreCommitToolOptions",
    "ProductionWorkspaceEditingComposition",
    "ProductionWorkspaceEditingOptions",
    "RunCommandsToolOptions",
    "SkillContextAugmentationOptions",
    "SkillScriptExecutionOptions",
    "SkillScriptPolicyEvaluationOptions",
    "StagedGitToolOptions",
    "ToolLoopRuntime",
    "create_apply_patch_registered_tool_adapter",
    "create_codex_commit_message_workflow",
    "create_codex_confirmed_commit_workflow",
    "create_codex_pydantic_ai_runtime",
    "create_codex_runtime",
    "create_commit_message_workflow",
    "create_confirmed_commit_workflow",
    "create_fetch_web_content_registered_tool_adapter",
    "create_interactive_tool_loop_runtime",
    "create_model_driven_skill_runtime",
    "create_pre_commit_registered_tool_adapters",
    "create_production_workspace_editing_composition",
    "create_pydantic_ai_model_driven_skill_runtime",
    "create_pydantic_ai_runtime",
    "create_pydantic_ai_tool_loop_runtime",
    "create_read_files_registered_tool_adapter",
    "create_run_commands_registered_tool_adapter",
    "create_search_codebase_registered_tool_adapter",
    "create_skill_augmented_local_agent_command",
    "create_skill_context_augmented_local_agent_command",
    "create_skill_context_loader",
    "create_skill_resource_augmented_local_agent_command",
    "create_skill_resource_context_loader",
    "create_skill_script_executor",
    "create_skill_script_policy_evaluator",
    "create_staged_git_registered_tools",
    "create_tool_loop_runtime",
]
