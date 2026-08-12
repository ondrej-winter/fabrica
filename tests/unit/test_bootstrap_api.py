"""Bootstrap public interface contract tests."""

from pathlib import Path

from fabrica import bootstrap

DEFAULT_STAGED_GIT_TOOL_TIMEOUT_SECONDS = 10.0
DEFAULT_PRE_COMMIT_TOOL_TIMEOUT_SECONDS = 120.0


EXPECTED_BOOTSTRAP_EXPORTS = [
    "DEFAULT_CODEX_AUTH_FILE",
    "DEFAULT_COMMIT_MESSAGE_CODEX_MODEL",
    "DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT",
    "CommitMessageWorkflow",
    "CommitMessageWorkflowOptions",
    "ConfirmedCommitWorkflow",
    "ConfirmedCommitWorkflowResult",
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


def test_bootstrap_exports_only_curated_composition_surface() -> None:
    """Document the stable consumer-facing bootstrap names."""
    assert bootstrap.__all__ == EXPECTED_BOOTSTRAP_EXPORTS
    assert all(hasattr(bootstrap, name) for name in bootstrap.__all__)
    assert "ReadOnlyGitContextToolOptions" not in bootstrap.__all__
    assert "create_read_only_git_context_registered_tools" not in bootstrap.__all__
    assert not hasattr(bootstrap, "ReadOnlyGitContextToolOptions")
    assert not hasattr(bootstrap, "create_read_only_git_context_registered_tools")


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


def test_product_cli_model_evidence_contract_uses_shared_kernel_owner() -> None:
    """Keep feature-neutral CLI evidence protocols pointed at the shared kernel."""
    bootstrap_cli_source = Path("src/fabrica/bootstrap/cli.py").read_text(encoding="utf-8")

    assert "from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence" in bootstrap_cli_source
    assert (
        "from fabrica.features.agent_runtime.application.dtos import (\n        ModelCostEvidence"
        not in bootstrap_cli_source
    )
