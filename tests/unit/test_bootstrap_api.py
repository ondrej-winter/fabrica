"""Bootstrap public interface contract tests."""

import sys
from pathlib import Path
from typing import NoReturn

from fabrica import bootstrap
from fabrica.adapters.inbound.cli import CliRegistrationError
from fabrica.bootstrap import cli as bootstrap_cli
from fabrica.bootstrap._composition_exports import (
    COMPOSITION_EXPORT_NAMES,
    ROOT_BOOTSTRAP_INTERNAL_ONLY_EXPORTS,
)

DEFAULT_STAGED_GIT_TOOL_TIMEOUT_SECONDS = 10.0
DEFAULT_PRE_COMMIT_TOOL_TIMEOUT_SECONDS = 120.0
EXPECTED_CLI_CONFIGURATION_ERROR_EXIT_CODE = 2


EXPECTED_BOOTSTRAP_EXPORTS = [
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


def test_bootstrap_export_map_reuses_composition_exports_with_explicit_exclusions() -> None:
    """Keep root bootstrap exports derived from one composition export map."""
    assert set(bootstrap.__all__) == set(COMPOSITION_EXPORT_NAMES) - ROOT_BOOTSTRAP_INTERNAL_ONLY_EXPORTS
    assert {
        "CommitMessageRuntime",
        "EvidenceRecordingCommitMessageRuntime",
        "ReadOnlyGitContextToolOptions",
        "create_read_only_git_context_registered_tools",
        "create_selected_context_local_agent_runtime",
    } == ROOT_BOOTSTRAP_INTERNAL_ONLY_EXPORTS


def test_bootstrap_package_import_does_not_eagerly_load_composition_modules() -> None:
    """Keep CLI startup resilient by avoiding package-level composition imports."""
    for module_name in tuple(sys.modules):
        if module_name.startswith("fabrica.bootstrap"):
            del sys.modules[module_name]

    bootstrap_package = __import__("fabrica.bootstrap", fromlist=["__all__"])

    assert bootstrap_package.__all__ == EXPECTED_BOOTSTRAP_EXPORTS
    assert "fabrica.bootstrap.composition" not in sys.modules
    assert "fabrica.bootstrap.composition.codex_runtime" not in sys.modules


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


def test_product_cli_translates_bootstrap_wiring_errors_to_stable_stderr(
    monkeypatch,
    capsys,
) -> None:
    """Keep expected composition failures from leaking tracebacks by default."""

    def fail_command_registration_creation(*, overrides: object | None = None) -> NoReturn:
        _ = overrides
        msg = "synthetic CLI wiring failure"
        raise CliRegistrationError(msg)

    monkeypatch.setattr(bootstrap_cli, "create_cli_command_registrars", fail_command_registration_creation)

    exit_code = bootstrap_cli.main(())

    assert exit_code == EXPECTED_CLI_CONFIGURATION_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: synthetic CLI wiring failure\n"
