"""Focused regression coverage for remaining Agent Runtime DTO and use-case guards."""

import asyncio
from dataclasses import dataclass, field
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    ActiveSkillCompactionState,
    ActiveSkillSet,
    LoadedSkillResourceContext,
    LocalAgentRunCommand,
    LocalAgentRunResult,
    RegisteredSkill,
    RegisteredToolOutcome,
    SelectedSkill,
    SelectedSkillResource,
    SelectedSkillScript,
    SelectedSkillToolDeclaration,
    SkillActivationCommand,
    SkillContextBounds,
    SkillDefinition,
    SkillRegistrySnapshot,
    SkillResourceContextBounds,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptMetadata,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyStatus,
    SkillScriptSandboxPolicy,
    SkillScriptType,
    SkillSource,
    SkillToolExposureStatus,
    SkillTrustBinding,
    SkillTrustEvaluationResult,
    SkillTrustEvaluationStatus,
    ToolExecutionRuntimeDisposition,
    ToolMutationGuarantee,
    ToolOutcomeStatus,
    tools,
)
from fabrica.features.agent_runtime.application.ports import SkillScriptMetadataLoadError
from fabrica.features.agent_runtime.application.use_cases import (
    ActivateSkill,
    CreateSkillRegistrySnapshot,
    EvaluateSkillScriptPolicy,
    LoadSkillContext,
    LoadSkillResourceContext,
    RehydrateActiveSkillContext,
    RunLocalAgentWithSelectedContext,
)


def test_skill_tool_declaration_uses_skill_identifier_without_label_or_tool() -> None:
    declaration = SelectedSkillToolDeclaration(
        skill_id="review-pr",
        status=SkillToolExposureStatus.DENIED,
    )

    assert declaration.display_label == "review-pr"


@pytest.mark.parametrize(
    ("skill_id", "source", "revision", "message"),
    [
        ("global:review-pr", SkillSource.WORKSPACE, "sha256:" + "a" * 64, "must match"),
        ("workspace:review-pr", SkillSource.WORKSPACE, "sha256:" + "A" * 64, "lowercase"),
    ],
)
def test_skill_trust_binding_rejects_inconsistent_identity(
    skill_id: str,
    source: SkillSource,
    revision: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        SkillTrustBinding(
            workspace_identity="workspace-1",
            run_id="run-1",
            skill_id=skill_id,
            source=source,
            revision=revision,
        )


def test_skill_trust_evaluation_rejects_definition_without_approval_and_reports_approval() -> None:
    binding = _trust_binding()
    definition = _skill_definition("review-pr")

    with pytest.raises(ValueError, match="only approved"):
        SkillTrustEvaluationResult(
            status=SkillTrustEvaluationStatus.UNTRUSTED,
            binding=binding,
            definition=definition,
        )

    approved = SkillTrustEvaluationResult(
        status=SkillTrustEvaluationStatus.APPROVED,
        binding=binding,
        definition=definition,
    )

    assert approved.approved is True


@pytest.mark.parametrize(
    ("status", "runtime_disposition", "error_code", "message"),
    [
        (ToolOutcomeStatus.SUCCESS, ToolExecutionRuntimeDisposition.CONTINUE_MODEL, "ERROR", "success outcomes"),
        (ToolOutcomeStatus.REJECTED, ToolExecutionRuntimeDisposition.CONTINUE_MODEL, None, "recoverable rejection"),
        (ToolOutcomeStatus.REJECTED, ToolExecutionRuntimeDisposition.STOP_RUNTIME, "ERROR", "must not stop"),
        (ToolOutcomeStatus.FATAL, ToolExecutionRuntimeDisposition.CONTINUE_MODEL, "ERROR", "fatal outcomes must stop"),
        (ToolOutcomeStatus.FATAL, ToolExecutionRuntimeDisposition.STOP_RUNTIME, None, "fatal outcomes must include"),
    ],
)
def test_tool_outcome_rejects_invalid_status_invariants(
    status: ToolOutcomeStatus,
    runtime_disposition: ToolExecutionRuntimeDisposition,
    error_code: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RegisteredToolOutcome(
            status=status,
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            runtime_disposition=runtime_disposition,
            error_code=error_code,
        )


def test_tool_outcome_serializes_missing_error_code_as_empty_payload() -> None:
    outcome = RegisteredToolOutcome.model_continue_success(
        mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
    )

    assert outcome._error_payload() == {}  # noqa: SLF001


def test_tool_failure_requires_an_error_code() -> None:
    with pytest.raises(ValueError, match="tool failure outcomes"):
        RegisteredToolOutcome(
            status=ToolOutcomeStatus.TOOL_FAILURE,
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
        )


def test_tool_failure_factory_and_finite_numbers_are_normalized() -> None:
    outcome = RegisteredToolOutcome.tool_failure(error_code="FAILED", error_message="failed")

    assert outcome.status is ToolOutcomeStatus.TOOL_FAILURE
    assert tools.canonical_tool_arguments_json({"value": 1.5}) == '{"value":1.5}'


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"value": float("inf")}, "numbers must be finite"),
        ({"value": "x" * 20_001}, "strings exceed"),
        ({str(index): index for index in range(101)}, "mapping entry bound"),
        ({"nested": {str(index): index for index in range(101)}}, "mappings exceed"),
    ],
)
def test_canonical_tool_arguments_reject_remaining_bounds(arguments: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        tools.canonical_tool_arguments_json(cast("dict[str, tools.ToolArgumentValue]", arguments))


def test_canonical_tool_arguments_reject_nested_bounds() -> None:
    nested: object = "nested"
    for _ in range(9):
        nested = (nested,)

    for arguments, message in (
        ({"value": nested}, "nesting depth"),
        ({"nested": {"x" * 20_001: "value"}}, "keys exceed"),
        ({"value": ("x",) * 101}, "sequences exceed"),
    ):
        with pytest.raises(ValueError, match=message):
            tools.canonical_tool_arguments_json(cast("dict[str, tools.ToolArgumentValue]", arguments))


def test_tool_private_validators_reject_unreachable_runtime_disposition_and_bad_digest() -> None:
    invalid_disposition = cast("ToolExecutionRuntimeDisposition", "unknown")
    outcome = RegisteredToolOutcome.model_continue_success(mutation_guarantee=ToolMutationGuarantee.NO_MUTATION)
    object.__setattr__(outcome, "runtime_disposition", invalid_disposition)

    with pytest.raises(ValueError, match="known runtime disposition"):
        tools._validate_success_outcome(outcome)  # noqa: SLF001
    with pytest.raises(ValueError, match="sha256 digest"):
        tools._validate_tool_digest("not-a-digest")  # noqa: SLF001


def test_registry_snapshot_rejects_more_than_maximum_enabled_skills() -> None:
    provider = _Provider(SkillSource.WORKSPACE, tuple(_skill_definition(f"skill-{index}") for index in range(51)))

    with pytest.raises(ValueError, match="enabled skill count"):
        CreateSkillRegistrySnapshot((provider,), snapshot_id_factory=lambda: "snapshot-1").create()


def test_script_policy_rejects_metadata_with_mismatched_binding_and_policy_violations() -> None:
    script = _script_selection()
    binding = _script_binding()
    mismatched_metadata = SkillScriptMetadata(
        selection=script,
        binding=binding,
    )
    evaluator = EvaluateSkillScriptPolicy(
        _MetadataLoader(metadata=mismatched_metadata),
        _ApprovalLookup(SkillScriptApprovalDecision(SkillScriptApprovalStatus.APPROVED, binding)),
    )

    result = evaluator.evaluate(
        SkillScriptPolicyEvaluationCommand(
            selection=script,
            sandbox_policy=SkillScriptSandboxPolicy(max_script_bytes=1),
        )
    )

    assert result.status is SkillScriptPolicyStatus.POLICY_VIOLATION


def test_script_policy_returns_metadata_error_for_loader_failure() -> None:
    script = _script_selection()
    result = EvaluateSkillScriptPolicy(_MetadataLoader(error=True), _ApprovalLookup()).evaluate(
        SkillScriptPolicyEvaluationCommand(selection=script),
    )

    assert result.status is SkillScriptPolicyStatus.METADATA_ERROR
    assert result.observations[0].metadata["category"] == "missing"


@pytest.mark.parametrize(
    ("metadata", "policy", "expected_category"),
    [
        (
            "selection_mismatch",
            SkillScriptSandboxPolicy(),
            "metadata_selection_mismatch",
        ),
        (
            "type_mismatch",
            SkillScriptSandboxPolicy(),
            "metadata_script_type_mismatch",
        ),
        (
            "valid",
            SkillScriptSandboxPolicy(allow_network=True),
            "network_access_not_supported",
        ),
        (
            "valid",
            SkillScriptSandboxPolicy(writable_path_labels=("workspace",)),
            "writable_paths_not_supported",
        ),
    ],
)
def test_script_policy_returns_remaining_metadata_and_policy_observations(
    metadata: str,
    policy: SkillScriptSandboxPolicy,
    expected_category: str,
) -> None:
    selection = _script_selection()
    binding = _script_binding()
    loaded_binding = (
        SkillScriptApprovalBinding(
            skill_id="review-pr",
            script_id="script.py",
            script_type=SkillScriptType.SHELL,
            suffix=".py",
            byte_size=4,
            content_digest="sha256:" + "a" * 64,
        )
        if metadata == "type_mismatch"
        else binding
    )
    loaded_selection = _script_selection(script_id="other.py") if metadata == "selection_mismatch" else selection
    script_metadata = SkillScriptMetadata(selection=selection, binding=loaded_binding)
    if metadata == "selection_mismatch":
        object.__setattr__(script_metadata, "selection", loaded_selection)
    result = EvaluateSkillScriptPolicy(
        _MetadataLoader(metadata=script_metadata),
        _ApprovalLookup(SkillScriptApprovalDecision(SkillScriptApprovalStatus.APPROVED, binding)),
    ).evaluate(SkillScriptPolicyEvaluationCommand(selection=selection, sandbox_policy=policy))

    assert result.observations[0].metadata["category"] == expected_category


def test_script_policy_rejects_structurally_malformed_environment_allowlist() -> None:
    selection = _script_selection()
    policy = SkillScriptSandboxPolicy()
    object.__setattr__(policy, "environment_allowlist", ("PATH",))

    observation = EvaluateSkillScriptPolicy(_MetadataLoader(), _ApprovalLookup())._policy_violation(  # noqa: SLF001
        selection,
        _script_binding(),
        policy,
    )

    assert observation is not None
    assert observation.metadata["category"] == "environment_access_not_supported"


def test_script_policy_rejects_structurally_unsupported_suffix() -> None:
    binding = _script_binding()
    object.__setattr__(binding, "suffix", ".unsupported")

    observation = EvaluateSkillScriptPolicy(_MetadataLoader(), _ApprovalLookup())._metadata_error(  # noqa: SLF001
        _script_selection(),
        SkillScriptMetadata(selection=_script_selection(), binding=binding),
    )

    assert observation is not None
    assert observation.metadata["category"] == "unsupported_script_suffix"


def test_skill_context_loader_rejects_remaining_loaded_bounds() -> None:
    for selection, definition, bounds, message in (
        (
            SelectedSkill(skill_id="review-pr"),
            _skill_definition("review-pr"),
            SkillContextBounds(max_label_chars=4),
            "identifier exceeds",
        ),
        (
            SelectedSkill(skill_id="id", label="x" * 5),
            _skill_definition("skill"),
            SkillContextBounds(max_label_chars=4),
            "label exceeds",
        ),
        (
            SelectedSkill(skill_id="skill"),
            _skill_definition_with_instructions("skill", "abcd"),
            SkillContextBounds(max_chars_per_skill=3),
            "per-skill",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            LoadSkillContext(_DefinitionLoader(definition), bounds=bounds).load((selection,))


def test_skill_context_loader_rejects_total_bound() -> None:
    definition = _skill_definition_with_instructions("skill", "abc")
    with pytest.raises(ValueError, match="total bound"):
        LoadSkillContext(_DefinitionLoader(definition), bounds=SkillContextBounds(max_total_chars=2)).load(
            (SelectedSkill(skill_id="skill"),)
        )


@pytest.mark.parametrize(
    ("resource_kwargs", "max_label_chars", "max_chars_per_resource", "message"),
    [
        ({"text": "abcd"}, 20, 3, "per-resource"),
        ({"skill_id": "x" * 5}, 4, 3, "identifier exceeds"),
        ({"resource_id": "x" * 21}, 20, 30, "resource identifier exceeds"),
    ],
)
def test_resource_context_loader_rejects_loaded_resource_bounds(
    resource_kwargs: dict[str, str],
    max_label_chars: int,
    max_chars_per_resource: int,
    message: str,
) -> None:
    resource = _resource(**resource_kwargs)
    loader = LoadSkillResourceContext(
        _ResourceLoader(resource),
        bounds=SkillResourceContextBounds(
            max_selected_resources=1,
            max_chars_per_resource=max_chars_per_resource,
            max_total_chars=max_chars_per_resource,
            max_label_chars=max_label_chars,
        ),
    )

    with pytest.raises(ValueError, match=message):
        loader.load((SelectedSkillResource(skill_id="review-pr", resource_id="reference.md"),))


def test_resource_context_loader_rejects_loaded_resource_display_label_bound() -> None:
    resource = LoadedSkillResourceContext(
        skill_id="skill",
        resource_id="reference.md",
        label="x" * 21,
        text="text",
    )
    loader = LoadSkillResourceContext(
        _ResourceLoader(resource),
        bounds=SkillResourceContextBounds(max_label_chars=20),
    )

    with pytest.raises(ValueError, match="resource label exceeds"):
        loader.load((SelectedSkillResource(skill_id="skill", resource_id="reference.md"),))


def test_rehydrator_rejects_non_positive_context_budget_and_defensive_none_state() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        RehydrateActiveSkillContext(max_total_context_chars=0)

    result = RehydrateActiveSkillContext(max_total_context_chars=1).rehydrate(
        LocalAgentRunCommand(prompt="x"),
        state=cast("ActiveSkillCompactionState", None),
        run_id="run-1",
        registry_snapshot_id="snapshot-1",
    )

    assert result.status.value == "malformed_state"


def test_activate_skill_rejects_invalid_timeout_and_evaluator_failure() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        ActivateSkill(_TrustEvaluator(), timeout_seconds=0)

    skill = _registered_skill()
    result = asyncio.run(
        ActivateSkill(_TrustEvaluator(error=True)).activate(
            _activation_command(skill),
            active_skills=ActiveSkillSet(run_id="run-1", registry_snapshot_id="snapshot-1"),
            cancellation=_NeverCancelled(),
        )
    )

    assert result.status.value == "internal_skill_error"


def test_activate_skill_rejects_post_evaluation_cancellation_and_active_state_conflicts() -> None:
    skill = _registered_skill()
    command = _activation_command(skill)
    active_skills = ActiveSkillSet(run_id="run-1", registry_snapshot_id="snapshot-1")
    cancellation = _CancellationAfterEvaluation()

    cancelled = asyncio.run(
        ActivateSkill(_ApprovedTrustEvaluator(skill.definition, cancellation=cancellation)).activate(
            command,
            active_skills=active_skills,
            cancellation=cancellation,
        )
    )

    assert cancelled.status.value == "skill_load_cancelled"
    active_skills.register(
        skill_id=skill.skill_id,
        revision="sha256:" + "b" * 64,
        instructions="older instructions",
    )
    conflict = asyncio.run(
        ActivateSkill(_ApprovedTrustEvaluator(skill.definition)).activate(
            command,
            active_skills=active_skills,
            cancellation=_NeverCancelled(),
        )
    )

    assert conflict.status.value == "internal_skill_error"


def test_activate_skill_rejects_cancellation_after_a_verified_evaluation() -> None:
    skill = _registered_skill()
    command = _activation_command(skill)
    cancellation = _AlreadyCancelled()
    evaluation = SkillTrustEvaluationResult(
        status=SkillTrustEvaluationStatus.APPROVED,
        binding=_trust_binding(),
        definition=skill.definition,
    )

    result = ActivateSkill(_ApprovedTrustEvaluator(skill.definition))._register_verified_skill(  # noqa: SLF001
        command,
        ActiveSkillSet(run_id="run-1", registry_snapshot_id="snapshot-1"),
        skill,
        evaluation,
        cancellation,
    )

    assert result.status.value == "skill_load_cancelled"


def test_activate_skill_rejects_mismatched_active_state_and_completed_cancellation_wait() -> None:
    skill = _registered_skill()
    command = _activation_command(skill)
    mismatched_state = ActiveSkillSet(run_id="other-run", registry_snapshot_id="snapshot-1")
    mismatch = asyncio.run(
        ActivateSkill(_ApprovedTrustEvaluator(skill.definition)).activate(
            command,
            active_skills=mismatched_state,
            cancellation=_NeverCancelled(),
        )
    )
    completed_wait = asyncio.run(
        ActivateSkill(_ApprovedTrustEvaluator(skill.definition)).activate(
            command,
            active_skills=ActiveSkillSet(run_id="run-1", registry_snapshot_id="snapshot-1"),
            cancellation=_ImmediateCancellationWait(),
        )
    )

    assert mismatch.status.value == "internal_skill_error"
    assert completed_wait.status.value == "skill_load_cancelled"


def test_selected_context_runtime_requires_resource_loader() -> None:
    use_case = RunLocalAgentWithSelectedContext(runtime=_Runtime())

    with pytest.raises(RuntimeError, match="resource context loader is not configured"):
        asyncio.run(
            use_case.run(
                LocalAgentRunCommand(prompt="Use resource"),
                resource_selections=(SelectedSkillResource(skill_id="review-pr", resource_id="reference.md"),),
            )
        )


def test_selected_context_runtime_delegates_without_selected_context() -> None:
    result = LocalAgentRunResult(status="success", output_text="done")  # ty: ignore[invalid-argument-type]
    runtime = _RecordingRuntime(result)

    received = asyncio.run(RunLocalAgentWithSelectedContext(runtime=runtime).run(LocalAgentRunCommand(prompt="Run")))

    assert received is result
    assert runtime.calls == [LocalAgentRunCommand(prompt="Run")]


@dataclass
class _Provider:
    source: SkillSource
    definitions: tuple[SkillDefinition, ...]

    def discover(self) -> tuple[SkillDefinition, ...]:
        return self.definitions


@dataclass
class _MetadataLoader:
    metadata: SkillScriptMetadata | None = None
    error: bool = False

    def load_metadata(self, selection: SelectedSkillScript) -> SkillScriptMetadata:
        del selection
        if self.error:
            msg = "missing"
            raise SkillScriptMetadataLoadError(
                msg,
                skill_id="review-pr",
                script_id="script.py",
                category="missing",
            )
        assert self.metadata is not None
        return self.metadata


@dataclass
class _ApprovalLookup:
    decision: SkillScriptApprovalDecision | None = None

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        del binding
        return self.decision or SkillScriptApprovalDecision(SkillScriptApprovalStatus.NOT_REQUESTED)


@dataclass
class _ResourceLoader:
    resource: LoadedSkillResourceContext

    def load(self, selection: SelectedSkillResource) -> LoadedSkillResourceContext:
        del selection
        return self.resource


@dataclass
class _DefinitionLoader:
    definition: SkillDefinition

    def load(self, selection: SelectedSkill) -> SkillDefinition:
        del selection
        return self.definition


@dataclass
class _TrustEvaluator:
    error: bool = False

    def evaluate(self, command: object) -> SkillTrustEvaluationResult:
        del command
        if self.error:
            raise RuntimeError
        return SkillTrustEvaluationResult(
            status=SkillTrustEvaluationStatus.UNTRUSTED,
            binding=_trust_binding(),
        )


class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        await asyncio.Event().wait()


class _AlreadyCancelled(_NeverCancelled):
    @property
    def is_cancelled(self) -> bool:
        return True


class _ImmediateCancellationWait(_NeverCancelled):
    async def wait_until_cancelled(self) -> None:
        return None


class _CancellationAfterEvaluation(_NeverCancelled):
    cancelled: bool = False

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled


@dataclass
class _ApprovedTrustEvaluator:
    definition: SkillDefinition
    cancellation: _CancellationAfterEvaluation | None = None

    def evaluate(self, command: object) -> SkillTrustEvaluationResult:
        del command
        if self.cancellation is not None:
            self.cancellation.cancelled = True
        return SkillTrustEvaluationResult(
            status=SkillTrustEvaluationStatus.APPROVED,
            binding=_trust_binding(),
            definition=self.definition,
        )


class _Runtime:
    async def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        del command
        msg = "runtime should not be invoked when the required loader is absent"
        raise AssertionError(msg)


@dataclass
class _RecordingRuntime:
    result: LocalAgentRunResult
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    async def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.result


def _skill_definition(name: str) -> SkillDefinition:
    return SkillDefinition.from_skill_file_bytes(
        name=name,
        description="Description.",
        instructions="# Instructions",
        skill_file_bytes=name.encode(),
    )


def _skill_definition_with_instructions(name: str, instructions: str) -> SkillDefinition:
    return SkillDefinition.from_skill_file_bytes(
        name=name,
        description="Description.",
        instructions=instructions,
        skill_file_bytes=f"{name}:{instructions}".encode(),
    )


def _script_selection(*, script_id: str = "script.py") -> SelectedSkillScript:
    return SelectedSkillScript(skill_id="review-pr", script_id=script_id)


def _script_binding() -> SkillScriptApprovalBinding:
    return SkillScriptApprovalBinding(
        skill_id="review-pr",
        script_id="script.py",
        script_type=SkillScriptType.PYTHON,
        suffix=".py",
        byte_size=4,
        content_digest="sha256:" + "a" * 64,
    )


def _registered_skill() -> RegisteredSkill:
    definition = _skill_definition("review-pr")
    return RegisteredSkill(skill_id="workspace:review-pr", source=SkillSource.WORKSPACE, definition=definition)


def _trust_binding() -> SkillTrustBinding:
    return SkillTrustBinding(
        workspace_identity="workspace-1",
        run_id="run-1",
        skill_id="workspace:review-pr",
        source=SkillSource.WORKSPACE,
        revision="sha256:" + "a" * 64,
    )


def _activation_command(skill: RegisteredSkill) -> SkillActivationCommand:
    return SkillActivationCommand(
        workspace_identity="workspace-1",
        run_id="run-1",
        snapshot=SkillRegistrySnapshot.create(snapshot_id="snapshot-1", skills=(skill,)),
        skill=skill.skill_id,
    )


def _resource(
    *,
    skill_id: str = "skill",
    resource_id: str = "reference.md",
    text: str = "text",
) -> LoadedSkillResourceContext:
    return LoadedSkillResourceContext(skill_id=skill_id, resource_id=resource_id, text=text)
