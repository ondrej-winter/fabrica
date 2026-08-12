"""Tests for CLI approval lookup adapters."""

from fabrica.features.agent_runtime.adapters.inbound.cli.approval import MetadataBoundCliApprovalLookup
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliScriptApprovalOptions,
    CliScriptExecuteCommand,
)
from fabrica.features.agent_runtime.application.dtos import (
    SkillScriptApprovalBinding,
    SkillScriptApprovalStatus,
    SkillScriptType,
)


def test_metadata_bound_cli_approval_lookup_approves_exact_cli_binding() -> None:
    binding = _binding()

    decision = MetadataBoundCliApprovalLookup(_command()).get_approval(binding)

    assert decision.status is SkillScriptApprovalStatus.APPROVED
    assert decision.binding == binding
    assert decision.reason is None


def test_metadata_bound_cli_approval_lookup_denies_mismatched_binding() -> None:
    binding = _binding(content_digest="sha256:changed")

    decision = MetadataBoundCliApprovalLookup(_command()).get_approval(binding)

    assert decision.status is SkillScriptApprovalStatus.DENIED
    assert decision.binding == binding
    assert decision.reason == "CLI approval metadata did not match selected script metadata"


def _command() -> CliScriptExecuteCommand:
    return CliScriptExecuteCommand(
        skill_id="python-testing",
        script_id="scripts/check.py",
        approval_options=CliScriptApprovalOptions(
            script_type=SkillScriptType.PYTHON,
            suffix=".py",
            byte_size=128,
            content_digest="sha256:abc123",
        ),
    )


def _binding(*, content_digest: str = "sha256:abc123") -> SkillScriptApprovalBinding:
    return SkillScriptApprovalBinding(
        skill_id="python-testing",
        script_id="scripts/check.py",
        script_type=SkillScriptType.PYTHON,
        suffix=".py",
        byte_size=128,
        content_digest=content_digest,
    )
