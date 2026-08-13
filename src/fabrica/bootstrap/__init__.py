"""Lazy public composition-root API for Fabrica."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "DEFAULT_CODEX_AUTH_FILE": "fabrica.bootstrap.composition.codex_runtime",
    "DEFAULT_COMMIT_MESSAGE_CODEX_MODEL": "fabrica.bootstrap.composition.codex_runtime",
    "DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT": "fabrica.bootstrap.composition.codex_runtime",
    "CommitMessageWorkflowOptions": "fabrica.bootstrap.composition.developer_workflow",
    "DenyByDefaultSkillScriptApprovalLookup": "fabrica.bootstrap.composition.skill_scripts",
    "ModelDrivenSkillRuntime": "fabrica.bootstrap.composition.tool_loop",
    "ModelDrivenSkillRuntimeOptions": "fabrica.bootstrap.composition.tool_loop",
    "PreCommitToolOptions": "fabrica.bootstrap.composition.developer_workflow",
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

__all__ = [
    "DEFAULT_CODEX_AUTH_FILE",
    "DEFAULT_COMMIT_MESSAGE_CODEX_MODEL",
    "DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT",
    "CommitMessageWorkflowOptions",
    "DenyByDefaultSkillScriptApprovalLookup",
    "ModelDrivenSkillRuntime",
    "ModelDrivenSkillRuntimeOptions",
    "PreCommitToolOptions",
    "SkillContextAugmentationOptions",
    "SkillScriptExecutionOptions",
    "SkillScriptPolicyEvaluationOptions",
    "StagedGitToolOptions",
    "ToolLoopRuntime",
    "create_codex_commit_message_workflow",
    "create_codex_confirmed_commit_workflow",
    "create_codex_pydantic_ai_runtime",
    "create_codex_runtime",
    "create_commit_message_workflow",
    "create_confirmed_commit_workflow",
    "create_model_driven_skill_runtime",
    "create_pre_commit_registered_tool_adapters",
    "create_pydantic_ai_model_driven_skill_runtime",
    "create_pydantic_ai_runtime",
    "create_pydantic_ai_tool_loop_runtime",
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


def __getattr__(name: str) -> Any:
    """Load public composition helpers on first access."""
    try:
        module_name = _EXPORT_MODULES[name]
    except KeyError as err:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg) from err
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
