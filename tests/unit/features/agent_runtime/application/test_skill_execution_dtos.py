"""Tests for selected Agent Skills script policy DTO contracts."""

from dataclasses import FrozenInstanceError
from hashlib import sha256
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS,
    DEFAULT_MAX_SKILL_SCRIPT_BYTES,
    DEFAULT_MAX_SKILL_SCRIPT_DIGEST_CHARS,
    DEFAULT_MAX_SKILL_SCRIPT_OBSERVATION_MESSAGE_CHARS,
    DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS,
    DEFAULT_SKILL_SCRIPT_TIMEOUT_SECONDS,
    SUPPORTED_SKILL_SCRIPT_SUFFIXES,
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptExecutionCommand,
    SkillScriptExecutionObservation,
    SkillScriptExecutionOutput,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptMetadata,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyEvaluationResult,
    SkillScriptPolicyObservation,
    SkillScriptPolicyStatus,
    SkillScriptSandboxPolicy,
    SkillScriptSnapshot,
    SkillScriptType,
    skill_script_type_for_suffix,
)

EXPECTED_DEFAULT_SKILL_SCRIPT_TIMEOUT_SECONDS = 10
EXPECTED_DEFAULT_MAX_SKILL_SCRIPT_BYTES = 64_000
EXPECTED_DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS = 8_000
EXPECTED_SCRIPT_BYTE_SIZE = 128
EXPECTED_SHORT_OUTPUT_BOUND = 5
EXPECTED_EXECUTION_DURATION_SECONDS = 0.5


def test_selected_skill_script_is_path_free_safe_and_immutable() -> None:
    metadata = {"source": "unit"}
    selection = SelectedSkillScript(
        skill_id="python-testing",
        script_id="scripts/check.py",
        label="Check script",
        metadata=metadata,
    )

    metadata["source"] = "changed"

    assert selection.skill_id == "python-testing"
    assert selection.script_id == "scripts/check.py"
    assert selection.display_label == "Check script"
    assert selection.metadata["source"] == "unit"
    with pytest.raises(TypeError):
        cast("dict[str, object]", selection.metadata)["source"] = "mutated"
    with pytest.raises(FrozenInstanceError):
        selection.script_id = "changed.py"  # ty: ignore[invalid-assignment]


def test_selected_skill_script_rejects_unsafe_identifiers_and_labels() -> None:
    with pytest.raises(ValueError, match="script_id must not be empty"):
        SelectedSkillScript(skill_id="python-testing", script_id="")
    with pytest.raises(ValueError, match="leading or trailing whitespace"):
        SelectedSkillScript(skill_id="python-testing", script_id=" scripts/check.py")
    with pytest.raises(ValueError, match="traversal segments"):
        SelectedSkillScript(skill_id="python-testing", script_id="../private.py")
    with pytest.raises(ValueError, match="relative script identifier"):
        SelectedSkillScript(skill_id="python-testing", script_id="/private.py")
    with pytest.raises(ValueError, match="unsupported characters"):
        SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py?raw=1")
    with pytest.raises(ValueError, match="safe script label bound"):
        SelectedSkillScript(
            skill_id="python-testing",
            script_id="x" * (DEFAULT_MAX_SAFE_SKILL_RESOURCE_LABEL_CHARS + 1),
        )


def test_script_type_mapping_is_narrow_and_suffix_based() -> None:
    assert frozenset((".py", ".sh")) == SUPPORTED_SKILL_SCRIPT_SUFFIXES
    assert skill_script_type_for_suffix(".py") is SkillScriptType.PYTHON
    assert skill_script_type_for_suffix(".sh") is SkillScriptType.SHELL
    assert skill_script_type_for_suffix(".js") is None


def test_approval_binding_contains_metadata_bound_script_identity() -> None:
    binding = _binding()

    assert binding.skill_id == "python-testing"
    assert binding.script_id == "scripts/check.py"
    assert binding.script_type is SkillScriptType.PYTHON
    assert binding.suffix == ".py"
    assert binding.byte_size == EXPECTED_SCRIPT_BYTE_SIZE
    assert binding.content_digest == "sha256:abc123"


def test_approval_binding_rejects_invalid_metadata() -> None:
    with pytest.raises(ValueError, match="script suffix"):
        SkillScriptApprovalBinding(
            skill_id="python-testing",
            script_id="scripts/check.js",
            script_type=SkillScriptType.PYTHON,
            suffix=".js",
            byte_size=128,
            content_digest="sha256:abc123",
        )
    with pytest.raises(ValueError, match="byte_size"):
        _binding(byte_size=0)
    with pytest.raises(ValueError, match="content_digest must not be empty"):
        _binding(content_digest="")
    with pytest.raises(ValueError, match="safe digest bound"):
        _binding(content_digest="x" * (DEFAULT_MAX_SKILL_SCRIPT_DIGEST_CHARS + 1))
    with pytest.raises(ValueError, match="content_digest contains unsupported characters"):
        _binding(content_digest="sha256:abc/123")


def test_script_metadata_requires_binding_to_match_selection() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    metadata = {"file_name": "check.py"}
    loaded = SkillScriptMetadata(selection=selection, binding=_binding(), metadata=metadata)

    metadata["file_name"] = "changed.py"

    assert loaded.binding == _binding()
    assert loaded.metadata["file_name"] == "check.py"
    with pytest.raises(TypeError):
        cast("dict[str, object]", loaded.metadata)["file_name"] = "mutated.py"
    with pytest.raises(ValueError, match="binding must match"):
        SkillScriptMetadata(selection=selection, binding=_binding(script_id="scripts/other.py"))


def test_script_snapshot_binds_immutable_content_to_selected_script_metadata() -> None:
    content = b"print('approved')\n"
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    metadata = {"file_name": "check.py"}
    snapshot = SkillScriptSnapshot(
        selection=selection,
        binding=_binding(byte_size=len(content), content_digest=f"sha256:{sha256(content).hexdigest()}"),
        content=content,
        metadata=metadata,
    )

    metadata["file_name"] = "changed.py"

    assert snapshot.content == content
    assert snapshot.metadata["file_name"] == "check.py"
    with pytest.raises(TypeError):
        cast("dict[str, object]", snapshot.metadata)["file_name"] = "mutated.py"
    with pytest.raises(FrozenInstanceError):
        snapshot.content = b"changed"  # ty: ignore[invalid-assignment]


def test_script_snapshot_rejects_content_that_does_not_match_binding() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    content = b"print('approved')\n"

    with pytest.raises(ValueError, match="binding must match"):
        SkillScriptSnapshot(selection=selection, binding=_binding(script_id="scripts/other.py"), content=content)
    with pytest.raises(ValueError, match="content length"):
        SkillScriptSnapshot(selection=selection, binding=_binding(byte_size=1), content=content)
    with pytest.raises(ValueError, match="content digest"):
        SkillScriptSnapshot(
            selection=selection,
            binding=_binding(byte_size=len(content), content_digest="sha256:not-current"),
            content=content,
        )


def test_approval_decision_models_non_interactive_statuses_and_immutability() -> None:
    metadata = {"source": "fake_approval"}
    decision = SkillScriptApprovalDecision(
        status=SkillScriptApprovalStatus.APPROVED,
        binding=_binding(),
        reason="approved by fixture",
        metadata=metadata,
    )

    metadata["source"] = "changed"

    assert decision.is_approved is True
    assert decision.metadata["source"] == "fake_approval"
    with pytest.raises(TypeError):
        cast("dict[str, object]", decision.metadata)["source"] = "mutated"
    assert SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.DENIED).is_approved is False
    assert SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.NOT_REQUESTED).is_approved is False
    assert SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.EXPIRED).is_approved is False


def test_sandbox_policy_defaults_are_deny_by_default_and_bounded() -> None:
    policy = SkillScriptSandboxPolicy()

    assert (
        policy.timeout_seconds == DEFAULT_SKILL_SCRIPT_TIMEOUT_SECONDS == EXPECTED_DEFAULT_SKILL_SCRIPT_TIMEOUT_SECONDS
    )
    assert policy.allow_network is False
    assert policy.writable_path_labels == ()
    assert policy.environment_allowlist == ()
    assert (
        policy.max_stdout_chars
        == DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS
        == EXPECTED_DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS
    )
    assert policy.max_stderr_chars == DEFAULT_MAX_SKILL_SCRIPT_OUTPUT_CHARS
    assert policy.max_script_bytes == DEFAULT_MAX_SKILL_SCRIPT_BYTES == EXPECTED_DEFAULT_MAX_SKILL_SCRIPT_BYTES


def test_sandbox_policy_rejects_unbounded_or_non_default_environment_access() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        SkillScriptSandboxPolicy(timeout_seconds=0)
    with pytest.raises(ValueError, match="max_stdout_chars"):
        SkillScriptSandboxPolicy(max_stdout_chars=-1)
    with pytest.raises(ValueError, match="max_stderr_chars"):
        SkillScriptSandboxPolicy(max_stderr_chars=-1)
    with pytest.raises(ValueError, match="max_script_bytes"):
        SkillScriptSandboxPolicy(max_script_bytes=0)
    with pytest.raises(ValueError, match="environment allowlist"):
        SkillScriptSandboxPolicy(environment_allowlist=("SAFE_NAME",))
    with pytest.raises(ValueError, match="writable_path_labels"):
        SkillScriptSandboxPolicy(writable_path_labels=("../private",))


def test_policy_evaluation_command_uses_default_sandbox_policy() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    command = SkillScriptPolicyEvaluationCommand(selection=selection)

    assert command.selection == selection
    assert command.sandbox_policy == SkillScriptSandboxPolicy()


def test_execution_command_uses_selected_script_and_default_sandbox_policy() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    command = SkillScriptExecutionCommand(selection=selection)

    assert command.selection == selection
    assert command.sandbox_policy == SkillScriptSandboxPolicy()


def test_execution_output_is_bounded_and_records_truncation_intent() -> None:
    output = SkillScriptExecutionOutput(text="hello", truncated=True, max_chars=EXPECTED_SHORT_OUTPUT_BOUND)

    assert output.text == "hello"
    assert output.truncated is True
    assert output.max_chars == EXPECTED_SHORT_OUTPUT_BOUND
    with pytest.raises(ValueError, match="output exceeds"):
        SkillScriptExecutionOutput(text="hello!", max_chars=EXPECTED_SHORT_OUTPUT_BOUND)
    with pytest.raises(ValueError, match="max_chars"):
        SkillScriptExecutionOutput(max_chars=-1)


def test_policy_observation_is_bounded_and_metadata_is_immutable() -> None:
    metadata = {"category": "denied"}
    observation = SkillScriptPolicyObservation(message="approval was denied", metadata=metadata)

    metadata["category"] = "changed"

    assert observation.metadata["category"] == "denied"
    with pytest.raises(TypeError):
        cast("dict[str, object]", observation.metadata)["category"] = "mutated"
    with pytest.raises(ValueError, match="message must not be empty"):
        SkillScriptPolicyObservation(message="")
    with pytest.raises(ValueError, match="safe observation bound"):
        SkillScriptPolicyObservation(message="x" * (DEFAULT_MAX_SKILL_SCRIPT_OBSERVATION_MESSAGE_CHARS + 1))


def test_execution_observation_is_bounded_and_metadata_is_immutable() -> None:
    metadata = {"category": "adapter_error"}
    observation = SkillScriptExecutionObservation(message="execution adapter failed", metadata=metadata)

    metadata["category"] = "changed"

    assert observation.metadata["category"] == "adapter_error"
    with pytest.raises(TypeError):
        cast("dict[str, object]", observation.metadata)["category"] = "mutated"
    with pytest.raises(ValueError, match="message must not be empty"):
        SkillScriptExecutionObservation(message="")
    with pytest.raises(ValueError, match="safe observation bound"):
        SkillScriptExecutionObservation(message="x" * (DEFAULT_MAX_SKILL_SCRIPT_OBSERVATION_MESSAGE_CHARS + 1))


def test_policy_evaluation_result_statuses_are_explicit_and_observations_are_immutable() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    observation = SkillScriptPolicyObservation(message="policy approved")
    result = SkillScriptPolicyEvaluationResult(
        status=SkillScriptPolicyStatus.APPROVED,
        selection=selection,
        binding=_binding(),
        observations=(observation,),
    )

    assert result.approved is True
    assert result.observations == (observation,)
    assert (
        SkillScriptPolicyEvaluationResult(status=SkillScriptPolicyStatus.DENIED, selection=selection).approved is False
    )
    assert (
        SkillScriptPolicyEvaluationResult(status=SkillScriptPolicyStatus.UNSUPPORTED, selection=selection).approved
        is False
    )
    assert (
        SkillScriptPolicyEvaluationResult(
            status=SkillScriptPolicyStatus.POLICY_VIOLATION,
            selection=selection,
        ).approved
        is False
    )
    assert (
        SkillScriptPolicyEvaluationResult(status=SkillScriptPolicyStatus.METADATA_ERROR, selection=selection).approved
        is False
    )


def test_execution_result_statuses_are_explicit_and_observations_are_immutable() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    observation = SkillScriptExecutionObservation(message="script executed")
    result = SkillScriptExecutionResult(
        status=SkillScriptExecutionStatus.SUCCESS,
        selection=selection,
        binding=_binding(),
        stdout=SkillScriptExecutionOutput(text="ok"),
        stderr=SkillScriptExecutionOutput(),
        exit_code=0,
        duration_seconds=EXPECTED_EXECUTION_DURATION_SECONDS,
        observations=(observation,),
    )

    assert result.succeeded is True
    assert result.stdout.text == "ok"
    assert result.stderr.text == ""
    assert result.exit_code == 0
    assert result.duration_seconds == EXPECTED_EXECUTION_DURATION_SECONDS
    assert result.observations == (observation,)
    for status in (
        SkillScriptExecutionStatus.POLICY_DENIED,
        SkillScriptExecutionStatus.EXECUTION_FAILED,
        SkillScriptExecutionStatus.TIMED_OUT,
        SkillScriptExecutionStatus.UNSUPPORTED,
        SkillScriptExecutionStatus.ADAPTER_ERROR,
    ):
        assert SkillScriptExecutionResult(status=status, selection=selection).succeeded is False


def test_execution_result_rejects_mismatched_binding_and_negative_duration() -> None:
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")

    with pytest.raises(ValueError, match="binding must match"):
        SkillScriptExecutionResult(
            status=SkillScriptExecutionStatus.SUCCESS,
            selection=selection,
            binding=_binding(script_id="scripts/other.py"),
        )
    with pytest.raises(ValueError, match="duration_seconds"):
        SkillScriptExecutionResult(
            status=SkillScriptExecutionStatus.SUCCESS,
            selection=selection,
            duration_seconds=-0.1,
        )


def _binding(
    *,
    script_id: str = "scripts/check.py",
    suffix: str = ".py",
    byte_size: int = EXPECTED_SCRIPT_BYTE_SIZE,
    content_digest: str = "sha256:abc123",
) -> SkillScriptApprovalBinding:
    script_type = skill_script_type_for_suffix(suffix)
    assert script_type is not None
    return SkillScriptApprovalBinding(
        skill_id="python-testing",
        script_id=script_id,
        script_type=script_type,
        suffix=suffix,
        byte_size=byte_size,
        content_digest=content_digest,
    )
