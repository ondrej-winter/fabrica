"""Lazy composition export map shared by bootstrap package façades."""

from __future__ import annotations

COMPOSITION_EXPORT_MODULES = {
    "DEFAULT_CODEX_AUTH_FILE": "fabrica.bootstrap.composition.codex_runtime",
    "DEFAULT_COMMIT_MESSAGE_CODEX_MODEL": "fabrica.bootstrap.composition.codex_runtime",
    "DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT": "fabrica.bootstrap.composition.codex_runtime",
    "CommitMessageRuntime": "fabrica.bootstrap.composition.developer_workflow",
    "CommitMessageWorkflowOptions": "fabrica.bootstrap.composition.developer_workflow",
    "DenyByDefaultSkillScriptApprovalLookup": "fabrica.bootstrap.composition.skill_scripts",
    "EvidenceRecordingCommitMessageRuntime": "fabrica.bootstrap.composition.developer_workflow",
    "ModelDrivenSkillRuntime": "fabrica.bootstrap.composition.tool_loop",
    "ModelDrivenSkillRuntimeOptions": "fabrica.bootstrap.composition.tool_loop",
    "PreCommitToolOptions": "fabrica.bootstrap.composition.developer_workflow",
    "ReadOnlyGitContextToolOptions": "fabrica.bootstrap.composition.developer_workflow",
    "SkillContextAugmentationOptions": "fabrica.bootstrap.composition.skill_context",
    "SkillScriptExecutionOptions": "fabrica.bootstrap.composition.skill_scripts",
    "SkillScriptPolicyEvaluationOptions": "fabrica.bootstrap.composition.skill_scripts",
    "StagedGitToolOptions": "fabrica.bootstrap.composition.developer_workflow",
    "ToolLoopRuntime": "fabrica.bootstrap.composition.tool_loop",
    "create_codex_commit_message_workflow": "fabrica.bootstrap.composition.developer_workflow",
    "create_codex_confirmed_commit_workflow": "fabrica.bootstrap.composition.developer_workflow",
    "create_codex_pydantic_ai_runtime": "fabrica.bootstrap.composition.codex_runtime",
    "create_codex_runtime": "fabrica.bootstrap.composition.codex_runtime",
    "create_commit_message_workflow": "fabrica.bootstrap.composition.developer_workflow",
    "create_confirmed_commit_workflow": "fabrica.bootstrap.composition.developer_workflow",
    "create_model_driven_skill_runtime": "fabrica.bootstrap.composition.tool_loop",
    "create_pre_commit_registered_tool_adapters": "fabrica.bootstrap.composition.developer_workflow",
    "create_pydantic_ai_model_driven_skill_runtime": "fabrica.bootstrap.composition.tool_loop",
    "create_pydantic_ai_runtime": "fabrica.bootstrap.composition.codex_runtime",
    "create_pydantic_ai_tool_loop_runtime": "fabrica.bootstrap.composition.tool_loop",
    "create_read_only_git_context_registered_tools": "fabrica.bootstrap.composition.developer_workflow",
    "create_selected_context_local_agent_runtime": "fabrica.bootstrap.composition.skill_context",
    "create_skill_augmented_local_agent_command": "fabrica.bootstrap.composition.skill_context",
    "create_skill_context_augmented_local_agent_command": "fabrica.bootstrap.composition.skill_context",
    "create_skill_context_loader": "fabrica.bootstrap.composition.skill_context",
    "create_skill_resource_augmented_local_agent_command": "fabrica.bootstrap.composition.skill_context",
    "create_skill_resource_context_loader": "fabrica.bootstrap.composition.skill_context",
    "create_skill_script_executor": "fabrica.bootstrap.composition.skill_scripts",
    "create_skill_script_policy_evaluator": "fabrica.bootstrap.composition.skill_scripts",
    "create_staged_git_registered_tools": "fabrica.bootstrap.composition.developer_workflow",
    "create_tool_loop_runtime": "fabrica.bootstrap.composition.tool_loop",
}

ROOT_BOOTSTRAP_INTERNAL_ONLY_EXPORTS = {
    "CommitMessageRuntime",
    "EvidenceRecordingCommitMessageRuntime",
    "ReadOnlyGitContextToolOptions",
    "create_read_only_git_context_registered_tools",
    "create_selected_context_local_agent_runtime",
}

ROOT_BOOTSTRAP_EXPORT_MODULES = {
    name: module
    for name, module in COMPOSITION_EXPORT_MODULES.items()
    if name not in ROOT_BOOTSTRAP_INTERNAL_ONLY_EXPORTS
}

COMPOSITION_EXPORT_NAMES = tuple(COMPOSITION_EXPORT_MODULES)
ROOT_BOOTSTRAP_EXPORT_NAMES = tuple(ROOT_BOOTSTRAP_EXPORT_MODULES)

__all__ = [
    "COMPOSITION_EXPORT_MODULES",
    "COMPOSITION_EXPORT_NAMES",
    "ROOT_BOOTSTRAP_EXPORT_MODULES",
    "ROOT_BOOTSTRAP_EXPORT_NAMES",
    "ROOT_BOOTSTRAP_INTERNAL_ONLY_EXPORTS",
]
