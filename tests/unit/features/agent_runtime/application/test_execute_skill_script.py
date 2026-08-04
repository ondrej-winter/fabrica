"""Tests for policy-gated selected Agent Skill script execution."""

from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptExecutionCommand,
    SkillScriptExecutionObservation,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptMetadata,
    SkillScriptType,
)
from fabrica.features.agent_runtime.application.ports import (
    SkillScriptExecutionError,
    SkillScriptMetadataLoadError,
)
from fabrica.features.agent_runtime.application.use_cases import EvaluateSkillScriptPolicy, ExecuteSkillScript


@dataclass
class FakeSkillScriptMetadataLoader:
    metadata_by_selection: dict[tuple[str, str], SkillScriptMetadata]
    calls: list[SelectedSkillScript] = field(default_factory=list)

    def load_metadata(self, selection: SelectedSkillScript) -> SkillScriptMetadata:
        self.calls.append(selection)
        try:
            return self.metadata_by_selection[(selection.skill_id, selection.script_id)]
        except KeyError as err:
            msg = "selected skill script metadata is unavailable"
            raise SkillScriptMetadataLoadError(
                msg,
                skill_id=selection.skill_id,
                script_id=selection.script_id,
                category="missing_script_metadata",
            ) from err


@dataclass
class FakeSkillScriptApprovalLookup:
    decisions_by_binding: dict[SkillScriptApprovalBinding, SkillScriptApprovalDecision]
    calls: list[SkillScriptApprovalBinding] = field(default_factory=list)

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        self.calls.append(binding)
        return self.decisions_by_binding.get(
            binding,
            SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.NOT_REQUESTED),
        )


@dataclass
class FakeSkillScriptExecutor:
    result: SkillScriptExecutionResult | None = None
    fail: bool = False
    calls: list[tuple[SkillScriptExecutionCommand, SkillScriptApprovalBinding]] = field(default_factory=list)

    def execute(
        self,
        command: SkillScriptExecutionCommand,
        approved_binding: SkillScriptApprovalBinding,
    ) -> SkillScriptExecutionResult:
        self.calls.append((command, approved_binding))
        if self.fail:
            msg = "execution adapter failed"
            raise SkillScriptExecutionError(
                msg,
                skill_id=command.selection.skill_id,
                script_id=command.selection.script_id,
                category="adapter_unavailable",
            )
        assert self.result is not None
        return self.result


def test_execute_calls_executor_when_policy_approves_matching_binding() -> None:
    selection = _selection()
    binding = _binding()
    expected = SkillScriptExecutionResult(
        status=SkillScriptExecutionStatus.SUCCESS,
        selection=selection,
        binding=binding,
        exit_code=0,
        observations=(SkillScriptExecutionObservation(message="script executed"),),
    )
    executor = FakeSkillScriptExecutor(result=expected)
    command = SkillScriptExecutionCommand(selection=selection)

    result = _use_case(selection, binding, executor=executor).execute(command)

    assert result == expected
    assert executor.calls == [(command, binding)]


def test_execute_denies_without_calling_executor_when_approval_is_absent() -> None:
    selection = _selection()
    binding = _binding()
    executor = FakeSkillScriptExecutor()
    policy_evaluator = EvaluateSkillScriptPolicy(
        FakeSkillScriptMetadataLoader(
            metadata_by_selection={
                _selection_key(selection): SkillScriptMetadata(selection=selection, binding=binding)
            },
        ),
        FakeSkillScriptApprovalLookup(decisions_by_binding={}),
    )

    result = ExecuteSkillScript(policy_evaluator, executor).execute(SkillScriptExecutionCommand(selection=selection))

    assert result.status is SkillScriptExecutionStatus.POLICY_DENIED
    assert result.binding == binding
    assert result.observations[0].metadata["policy_status"] == "denied"
    assert executor.calls == []


def test_execute_denies_without_calling_executor_when_metadata_fails() -> None:
    selection = _selection(script_id="scripts/missing.py")
    executor = FakeSkillScriptExecutor()
    policy_evaluator = EvaluateSkillScriptPolicy(
        FakeSkillScriptMetadataLoader(metadata_by_selection={}),
        FakeSkillScriptApprovalLookup(decisions_by_binding={}),
    )

    result = ExecuteSkillScript(policy_evaluator, executor).execute(SkillScriptExecutionCommand(selection=selection))

    assert result.status is SkillScriptExecutionStatus.POLICY_DENIED
    assert result.binding is None
    assert result.observations[0].metadata["policy_status"] == "metadata_error"
    assert executor.calls == []


def test_execute_denies_without_calling_executor_when_policy_has_no_binding() -> None:
    selection = _selection()
    executor = FakeSkillScriptExecutor()
    policy_evaluator = EvaluateSkillScriptPolicy(
        FakeSkillScriptMetadataLoader(metadata_by_selection={}),
        FakeSkillScriptApprovalLookup(decisions_by_binding={}),
    )

    result = ExecuteSkillScript(policy_evaluator, executor).execute(SkillScriptExecutionCommand(selection=selection))

    assert result.status is SkillScriptExecutionStatus.POLICY_DENIED
    assert result.binding is None
    assert executor.calls == []


def test_execute_maps_unexpected_executor_error_to_adapter_error_result() -> None:
    selection = _selection()
    binding = _binding()
    executor = FakeSkillScriptExecutor(fail=True)

    result = _use_case(selection, binding, executor=executor).execute(SkillScriptExecutionCommand(selection=selection))

    assert result.status is SkillScriptExecutionStatus.ADAPTER_ERROR
    assert result.binding == binding
    assert result.observations[0].metadata == {
        "skill_id": "python-testing",
        "script_id": "scripts/check.py",
        "category": "adapter_unavailable",
    }


def _use_case(
    selection: SelectedSkillScript,
    binding: SkillScriptApprovalBinding,
    *,
    executor: FakeSkillScriptExecutor,
) -> ExecuteSkillScript:
    policy_evaluator = EvaluateSkillScriptPolicy(
        FakeSkillScriptMetadataLoader(
            metadata_by_selection={
                _selection_key(selection): SkillScriptMetadata(selection=selection, binding=binding)
            },
        ),
        FakeSkillScriptApprovalLookup(
            decisions_by_binding={
                binding: SkillScriptApprovalDecision(
                    status=SkillScriptApprovalStatus.APPROVED,
                    binding=binding,
                ),
            },
        ),
    )
    return ExecuteSkillScript(policy_evaluator, executor)


def _selection(*, script_id: str = "scripts/check.py") -> SelectedSkillScript:
    return SelectedSkillScript(skill_id="python-testing", script_id=script_id)


def _selection_key(selection: SelectedSkillScript) -> tuple[str, str]:
    return (selection.skill_id, selection.script_id)


def _binding() -> SkillScriptApprovalBinding:
    return SkillScriptApprovalBinding(
        skill_id="python-testing",
        script_id="scripts/check.py",
        script_type=SkillScriptType.PYTHON,
        suffix=".py",
        byte_size=128,
        content_digest="sha256:abc123",
    )
