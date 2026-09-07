"""Additional boundary-validation coverage for agent-runtime DTOs."""

from datetime import UTC, datetime
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS,
    DEFAULT_MAX_SELECTED_SKILLS,
    ActiveSkill,
    ActiveSkillCompactionState,
    ActiveSkillSet,
    CompletionCommitResult,
    CompletionCommitStatus,
    CompletionOutcome,
    CompletionRecord,
    CompletionVerification,
    ModelTurnInstruction,
    RegisteredSkill,
    RegisteredToolOutcome,
    SelectedSkill,
    SelectedSkillToolDeclaration,
    SkillDefinition,
    SkillRegistrySnapshot,
    SkillResolution,
    SkillResolutionStatus,
    SkillSource,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    SkillTrustBinding,
    SkillTrustEvaluationCommand,
    SkillTrustEvaluationResult,
    SkillTrustEvaluationStatus,
    ToolCallRequest,
    ToolExecutionRuntimeDisposition,
    ToolMutationGuarantee,
    ToolOutcomeStatus,
    canonical_tool_arguments_digest,
    completion,
    skill_activation,
    skill_compaction,
    skill_definitions,
    skill_execution,
    skill_registry,
    skill_tools,
    skill_trust,
    tools,
)
from fabrica.features.agent_runtime.application.ports import CompletionGuardRejectionError


def test_completion_records_and_results_reject_invalid_durable_state() -> None:
    record = _record()

    with pytest.raises(ValueError, match="payload digest"):
        CompletionRecord(
            run_id=record.run_id,
            tool_call_id=record.tool_call_id,
            payload_digest="invalid",
            outcome=record.outcome,
            summary=record.summary,
            verification=record.verification,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        CompletionRecord(
            run_id="run-1",
            tool_call_id="call-1",
            payload_digest="sha256:" + "a" * 64,
            outcome=CompletionOutcome.COMPLETED,
            summary="Done.",
            verification=CompletionVerification.VERIFIED,
            committed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    with pytest.raises(ValueError, match="must not carry"):
        CompletionCommitResult(status=CompletionCommitStatus.CANCELLED, record=record)
    with pytest.raises(ValueError, match="must carry"):
        CompletionCommitResult(status=CompletionCommitStatus.COMMITTED)


def test_model_turn_instruction_rejects_empty_and_oversized_values() -> None:
    with pytest.raises(ValueError, match="type must not be empty"):
        ModelTurnInstruction(instruction_type="", text="Use the completion tool.")
    with pytest.raises(ValueError, match="text must contain"):
        ModelTurnInstruction(instruction_type="completion", text="")


def test_active_skill_and_compaction_boundaries_reject_invalid_identity() -> None:
    with pytest.raises(ValueError, match="active skill ID"):
        ActiveSkill("", "sha256:" + "a" * 64, "instructions", 0, "snapshot-1")
    with pytest.raises(ValueError, match="activation order"):
        ActiveSkill("workspace:review-pr", "sha256:" + "a" * 64, "instructions", -1, "snapshot-1")
    with pytest.raises(ValueError, match="run ID"):
        ActiveSkillSet(run_id="", registry_snapshot_id="snapshot-1")
    with pytest.raises(ValueError, match="compacted active skill run ID"):
        ActiveSkillCompactionState(run_id="", registry_snapshot_id="snapshot-1", skills=())


def test_skill_definition_rejects_disabled_type_and_metadata_boundaries() -> None:
    kwargs = _definition_kwargs()
    with pytest.raises(TypeError, match="disabled flag"):
        SkillDefinition(**{**kwargs, "disabled": "false"})  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="metadata numbers must be finite"):
        SkillDefinition(**{**kwargs, "metadata": {"value": float("nan")}})  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="metadata keys must be strings"):
        SkillDefinition(**{**kwargs, "metadata": {1: "value"}})  # ty: ignore[invalid-argument-type]


def test_skill_registry_rejects_invalid_registered_resolution_and_snapshot_shapes() -> None:
    skill = _registered_skill()
    with pytest.raises(ValueError, match="must match"):
        RegisteredSkill(skill_id="global:review-pr", source=SkillSource.WORKSPACE, definition=skill.definition)
    with pytest.raises(ValueError, match="found skill resolution"):
        SkillResolution(status=SkillResolutionStatus.FOUND)
    with pytest.raises(ValueError, match="at least two candidates"):
        SkillResolution(status=SkillResolutionStatus.AMBIGUOUS, candidates=("workspace:review-pr",))
    with pytest.raises(ValueError, match="snapshot ID"):
        SkillRegistrySnapshot(snapshot_id=" ", registry_revision="sha256:" + "a" * 64, skills=())


def test_skill_tool_and_trust_dtos_reject_invalid_boundary_values() -> None:
    with pytest.raises(ValueError, match="selected skill count"):
        SkillToolPreparationCommand(
            selected_skills=tuple(_selected_skill() for _ in range(DEFAULT_MAX_SELECTED_SKILLS + 1))
        )
    with pytest.raises(ValueError, match="label must not be empty"):
        SelectedSkillToolDeclaration(skill_id="python-testing", status=SkillToolExposureStatus.DENIED, label="")
    with pytest.raises(ValueError, match="workspace_identity"):
        SkillTrustBinding(
            workspace_identity="",
            run_id="run-1",
            skill_id="workspace:review-pr",
            source=SkillSource.WORKSPACE,
            revision="sha256:" + "a" * 64,
        )
    with pytest.raises(ValueError, match="approved skill trust"):
        SkillTrustEvaluationResult(status=SkillTrustEvaluationStatus.APPROVED, binding=_binding())
    with pytest.raises(ValueError, match="canonical"):
        SkillTrustEvaluationCommand(
            workspace_identity="workspace-1",
            run_id="run-1",
            skill=_registered_skill(),
            allowed_skill_ids=frozenset({"review-pr"}),
        )


def test_tool_outcome_and_argument_boundaries_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="result text exceeds"):
        RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            result_text="x" * 20_001,
        )
    with pytest.raises(ValueError, match="tool failure outcomes"):
        RegisteredToolOutcome(
            status=ToolOutcomeStatus.TOOL_FAILURE, mutation_guarantee=ToolMutationGuarantee.NO_MUTATION
        )
    with pytest.raises(ValueError, match="recoverable rejection outcomes"):
        RegisteredToolOutcome(
            status=ToolOutcomeStatus.REJECTED,
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            error_code="REJECTED",
            runtime_disposition=ToolExecutionRuntimeDisposition.STOP_RUNTIME,
        )
    with pytest.raises(TypeError, match="tool arguments must be a mapping"):
        canonical_tool_arguments_digest([])  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="numbers must be finite"):
        ToolCallRequest(call_id="call-1", tool_name="tool", arguments={"value": float("inf")})


def test_completion_guard_rejection_only_accepts_guard_codes() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        CompletionGuardRejectionError(
            code=CompletionCommitStatus.CANCELLED,  # ty: ignore[invalid-argument-type]
            message="invalid",
        )


@pytest.mark.parametrize("value", ["", "has/slash", "x" * 121])
def test_completion_identifier_guard_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="bounded non-empty identifier"):
        completion._validate_identifier(value, field_name="run id")  # noqa: SLF001


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: ActiveSkill("skill", "bad", "instructions", 0, "snapshot"), "revision"),
        (lambda: ActiveSkill("skill", "sha256:" + "a" * 64, "", 0, "snapshot"), "instructions"),
        (lambda: ActiveSkill("skill", "sha256:" + "a" * 64, "instructions", 0, ""), "snapshot ID"),
        (lambda: ActiveSkillSet("run", ""), "snapshot ID"),
    ],
)
def test_active_skill_dtos_reject_remaining_invalid_values(factory, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_active_skill_set_rejects_duplicate_and_replaced_revisions() -> None:
    active = ActiveSkillSet(run_id="run", registry_snapshot_id="snapshot")
    active.register(skill_id="workspace:review-pr", revision="sha256:" + "a" * 64, instructions="first")

    with pytest.raises(ValueError, match="already active"):
        active.register(skill_id="workspace:review-pr", revision="sha256:" + "a" * 64, instructions="first")
    with pytest.raises(ValueError, match="silently replaced"):
        active.register(skill_id="workspace:review-pr", revision="sha256:" + "b" * 64, instructions="second")


def test_skill_activation_command_rejects_invalid_boundary_values() -> None:
    snapshot = SkillRegistrySnapshot.create(snapshot_id="snapshot", skills=())
    for kwargs, error_type, message in (
        ({"workspace_identity": ""}, ValueError, "workspace identity"),
        ({"run_id": ""}, ValueError, "run ID"),
        ({"skill": 1}, TypeError, "invocation"),
        ({"args": 1}, TypeError, "arguments"),
    ):
        with pytest.raises(error_type, match=message):
            skill_activation.SkillActivationCommand(
                workspace_identity=cast("str", kwargs.get("workspace_identity", "workspace")),
                run_id=cast("str", kwargs.get("run_id", "run")),
                snapshot=snapshot,
                skill=cast("str", kwargs.get("skill", "review-pr")),
                args=cast("str | None", kwargs.get("args")),
            )


def test_compaction_state_rejects_missing_snapshot_identity() -> None:
    with pytest.raises(ValueError, match="snapshot ID"):
        skill_compaction.ActiveSkillCompactionState(run_id="run", registry_snapshot_id="", skills=())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("name", "x" * 65, "name exceeds"),
        ("description", " description", "leading or trailing"),
        ("description", "x" * 513, "description exceeds"),
        ("metadata", {"deep": {"x": {"y": {"z": {"a": {"b": {"c": {"d": {"e": 1}}}}}}}}}, "nesting depth"),
    ],
)
def test_skill_definition_guards_reject_remaining_bounds(field: str, value: object, message: str) -> None:
    kwargs = _definition_kwargs()
    kwargs[field] = value
    with pytest.raises(ValueError, match=message):
        skill_definitions.SkillDefinition(**kwargs)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: skill_execution.SelectedSkillScript(skill_id="", script_id="script.py"), "skill_id"),
        (lambda: skill_execution.SelectedSkillScript(skill_id="skill", script_id="/script.py"), "relative script"),
        (
            lambda: skill_execution.SkillScriptApprovalBinding(
                "skill", "script.py", skill_execution.SkillScriptType.PYTHON, ".py", 1, " bad"
            ),
            "leading or trailing",
        ),
        (lambda: skill_execution.SkillScriptSandboxPolicy(environment_allowlist=("SAFE",)), "environment allowlist"),
        (lambda: skill_execution.SkillScriptExecutionOutput(max_chars=-1), "max_chars"),
        (lambda: skill_execution.SkillScriptPolicyObservation(message=" bad"), "leading or trailing"),
        (lambda: skill_execution.SkillScriptExecutionObservation(message=" bad"), "leading or trailing"),
    ],
)
def test_skill_execution_dto_guards_reject_remaining_invalid_values(factory, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_registry_and_trust_private_boundary_guards_reject_invalid_values() -> None:
    with pytest.raises(TypeError, match="invocation must be a string"):
        skill_registry._normalize_invocation(cast("str", 1))  # noqa: SLF001
    with pytest.raises(ValueError, match="invocation must not be empty"):
        skill_registry._normalize_invocation(" / ")  # noqa: SLF001
    with pytest.raises(ValueError, match="safe non-empty"):
        skill_trust._validate_context_identity("bad value", field_name="run_id")  # noqa: SLF001
    with pytest.raises(ValueError, match="label exceeds"):
        skill_tools._validate_safe_skill_tool_text(  # noqa: SLF001
            "x" * (DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS + 1),
            field_name="label",
        )
    with pytest.raises(ValueError, match="reason must not be empty"):
        skill_tools._validate_skill_tool_reason("")  # noqa: SLF001


def test_tool_private_guards_reject_remaining_invalid_values() -> None:
    with pytest.raises(ValueError, match="error message exceeds"):
        tools.RegisteredToolOutcome.recoverable_rejection(error_code="REJECTED", error_message="x" * 1_001)
    with pytest.raises(ValueError, match="max_chars must be at least"):
        tools.RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
        ).to_bounded_json(max_chars=0)
    with pytest.raises(ValueError, match="model output text exceeds"):
        tools.ToolAwareModelResponse(output_text="x" * 20_001)
    with pytest.raises(ValueError, match="mapping entry bound"):
        tools.canonical_tool_arguments_json({str(index): index for index in range(101)})
    with pytest.raises(TypeError, match="keys must be strings"):
        tools.canonical_tool_arguments_json({"nested": {1: "value"}})  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="digest must use lowercase"):
        tools._validate_tool_digest("sha256:" + "A" * 64)  # noqa: SLF001


def test_remaining_completion_activation_and_skill_result_helpers() -> None:
    with pytest.raises(ValueError, match="summary"):
        CompletionRecord(
            run_id="run",
            tool_call_id="call",
            payload_digest="sha256:" + "a" * 64,
            outcome=CompletionOutcome.COMPLETED,
            summary="",
            verification=CompletionVerification.VERIFIED,
        )
    assert skill_activation.SkillActivationResult(skill_activation.SkillActivationStatus.ACTIVATED, None).succeeded
    assert not skill_activation.SkillActivationResult(
        skill_activation.SkillActivationStatus.SKILL_NOT_FOUND, None
    ).succeeded


def test_skill_definition_registry_and_execution_remaining_guards() -> None:
    with pytest.raises(ValueError, match="disabled"):
        RegisteredSkill(
            skill_id="workspace:review-pr",
            source=SkillSource.WORKSPACE,
            definition=SkillDefinition(**{**_definition_kwargs(), "disabled": True}),  # ty: ignore[invalid-argument-type]
        )
    with pytest.raises(ValueError, match="only found"):
        SkillResolution(status=SkillResolutionStatus.MISSING, skill=_registered_skill())
    with pytest.raises(ValueError, match="unique and sorted"):
        SkillResolution(
            status=SkillResolutionStatus.AMBIGUOUS,
            candidates=("workspace:z", "workspace:a"),
        )
    with pytest.raises(ValueError, match="only ambiguous"):
        SkillResolution(status=SkillResolutionStatus.MISSING, candidates=("workspace:review-pr",))


def test_skill_definition_metadata_guards_cover_bounded_json_values() -> None:
    finite_value = 1.5
    assert skill_definitions._normalize_skill_metadata_value(finite_value, depth=1) == finite_value  # noqa: SLF001
    with pytest.raises(ValueError, match="strings exceed"):
        skill_definitions._normalize_skill_metadata_value("x" * 20_001, depth=1)  # noqa: SLF001
    with pytest.raises(ValueError, match="sequences exceed"):
        skill_definitions._normalize_skill_metadata_value([0] * 101, depth=1)  # noqa: SLF001
    with pytest.raises(TypeError, match="JSON-like"):
        skill_definitions._normalize_skill_metadata_value(object(), depth=1)  # noqa: SLF001
    with pytest.raises(ValueError, match="mappings exceed"):
        skill_definitions._normalize_skill_metadata_mapping(  # noqa: SLF001
            {str(index): index for index in range(101)},
            depth=1,
        )
    with pytest.raises(ValueError, match="keys exceed"):
        skill_definitions._normalize_skill_metadata_mapping({"x" * 20_001: 1}, depth=1)  # noqa: SLF001


def test_skill_execution_and_registry_remaining_guards() -> None:
    for value, message in (
        ("", "must not be empty"),
        ("x" * (DEFAULT_MAX_SAFE_SKILL_LABEL_CHARS + 1), "skill label bound"),
        (" bad", "leading or trailing"),
    ):
        with pytest.raises(ValueError, match=message):
            skill_execution._validate_safe_skill_text(value, field_name="skill_id")  # noqa: SLF001
    for value, message in (("/bad", "relative identifier"), ("../bad", "traversal"), ("bad?", "unsupported")):
        with pytest.raises(ValueError, match=message):
            skill_execution._validate_safe_skill_text(value, field_name="skill_id")  # noqa: SLF001
    for value, message in (("", "must not be empty"), ("1NAME", "must not start"), ("BAD-NAME", "unsupported")):
        with pytest.raises(ValueError, match=message):
            skill_execution._validate_environment_name(value)  # noqa: SLF001
    with pytest.raises(ValueError, match="environment allowlist"):
        skill_execution.SkillScriptSandboxPolicy(environment_allowlist=("SAFE",))
    skill = _registered_skill()
    with pytest.raises(ValueError, match="revision"):
        SkillRegistrySnapshot(snapshot_id="snapshot", registry_revision="bad", skills=())
    with pytest.raises(ValueError, match="enabled skill bound"):
        SkillRegistrySnapshot(
            snapshot_id="snapshot",
            registry_revision="sha256:" + "a" * 64,
            skills=tuple(skill for _ in range(51)),
        )
    with pytest.raises(ValueError, match="unique"):
        SkillRegistrySnapshot(
            snapshot_id="snapshot",
            registry_revision="sha256:" + "a" * 64,
            skills=(skill, skill),
        )
    with pytest.raises(ValueError, match="sorted"):
        SkillRegistrySnapshot(
            snapshot_id="snapshot",
            registry_revision="sha256:" + "a" * 64,
            skills=(_registered_skill(source=SkillSource.WORKSPACE), _registered_skill(source=SkillSource.GLOBAL)),
        )


def _definition_kwargs() -> dict[str, object]:
    return {
        "name": "review-pr",
        "description": "Review pull requests.",
        "instructions": "# Review",
        "revision": "sha256:" + "a" * 64,
    }


def _registered_skill(*, source: SkillSource = SkillSource.WORKSPACE) -> RegisteredSkill:
    return RegisteredSkill(
        skill_id=f"{source.value}:review-pr",
        source=source,
        definition=SkillDefinition(**_definition_kwargs()),  # ty: ignore[invalid-argument-type]
    )


def _binding() -> SkillTrustBinding:
    return SkillTrustBinding(
        workspace_identity="workspace-1",
        run_id="run-1",
        skill_id="workspace:review-pr",
        source=SkillSource.WORKSPACE,
        revision="sha256:" + "a" * 64,
    )


def _record() -> CompletionRecord:
    return CompletionRecord(
        run_id="run-1",
        tool_call_id="call-1",
        payload_digest="sha256:" + "a" * 64,
        outcome=CompletionOutcome.COMPLETED,
        summary="Done.",
        verification=CompletionVerification.VERIFIED,
    )


def _selected_skill() -> SelectedSkill:
    return SelectedSkill(skill_id="python-testing")
