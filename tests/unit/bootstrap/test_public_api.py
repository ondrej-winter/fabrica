"""Bootstrap public API and documentation contract tests."""

from pathlib import Path

from fabrica import bootstrap

DEFAULT_STAGED_GIT_TOOL_TIMEOUT_SECONDS = 10.0
DEFAULT_PRE_COMMIT_TOOL_TIMEOUT_SECONDS = 120.0

EXPECTED_BOOTSTRAP_EXPORTS = [
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


def test_bootstrap_exports_only_curated_composition_surface() -> None:
    """Document the stable consumer-facing bootstrap names."""
    assert bootstrap.__all__ == EXPECTED_BOOTSTRAP_EXPORTS
    assert all(getattr(bootstrap, name) is not None for name in bootstrap.__all__)
    assert "CommitMessageWorkflow" not in bootstrap.__all__
    assert "ConfirmedCommitWorkflow" not in bootstrap.__all__
    assert "ConfirmedCommitWorkflowResult" not in bootstrap.__all__
    assert "ReadOnlyGitContextToolOptions" not in bootstrap.__all__
    assert "create_read_only_git_context_registered_tools" not in bootstrap.__all__
    assert not hasattr(bootstrap, "ReadOnlyGitContextToolOptions")
    assert not hasattr(bootstrap, "create_read_only_git_context_registered_tools")


def test_readme_uses_current_bootstrap_runtime_helper_names() -> None:
    """Keep documented Python API examples aligned with exported bootstrap names."""
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "create_codex_runtime" in readme
    assert "create_pydantic_ai_runtime" in readme
    assert "create_codex_pydantic_ai_runtime" in readme
    assert "create_codex_local_agent_runtime" not in readme
    assert "create_pydantic_ai_local_agent_runtime" not in readme
    assert "create_codex_pydantic_ai_local_agent_runtime" not in readme
    assert "create_registered_tool_loop_runtime" not in readme
    assert "create_pydantic_ai_registered_tool_loop_runtime" not in readme


def test_readme_documents_opt_in_interactive_ask_question_composition() -> None:
    """Keep public interactive-runtime guidance aligned with the bootstrap API."""
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "create_interactive_tool_loop_runtime" in readme
    assert "InteractionTransport" in readme
    assert "create_tool_loop_runtime()" in readme
    assert "does not\nexpose `ask_question`" in readme
    assert "must not fabricate an answer" in readme


def test_readme_documents_fetch_web_content_composition_and_safety_boundary() -> None:
    """Keep public-web onboarding aligned with the explicit composition contract."""
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "FetchWebContentToolOptions" in readme
    assert "create_fetch_web_content_registered_tool_adapter" in readme
    assert "public_web_enabled=False" in readme
    assert "PUBLIC_WEB_DISABLED" in readme
    assert "untrusted_web_content" in readme
    assert "connection-level DNS address pinning" in readme
    assert "fetch_web_content" in readme


def test_bootstrap_option_defaults_preserve_safe_composition_contract() -> None:
    """Document safety-relevant defaults for bootstrap option DTOs."""
    script_policy = bootstrap.SkillScriptPolicyEvaluationOptions()
    script_execution = bootstrap.SkillScriptExecutionOptions()
    pre_commit_tools = bootstrap.PreCommitToolOptions()
    staged_git_tools = bootstrap.StagedGitToolOptions()
    model_skill_runtime = bootstrap.ModelDrivenSkillRuntimeOptions()

    assert script_policy.approval_lookup is None
    assert script_execution.approval_lookup is None
    assert script_execution.working_directory is None
    assert pre_commit_tools.working_directory is None
    assert pre_commit_tools.timeout_seconds == DEFAULT_PRE_COMMIT_TOOL_TIMEOUT_SECONDS
    assert staged_git_tools.working_directory is None
    assert staged_git_tools.timeout_seconds == DEFAULT_STAGED_GIT_TOOL_TIMEOUT_SECONDS
    assert model_skill_runtime.skill_tools == ()
