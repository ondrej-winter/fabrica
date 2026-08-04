"""Use case for policy-gated selected Agent Skill script execution."""

from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptExecutionCommand,
    SkillScriptExecutionObservation,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyEvaluationResult,
    SkillScriptSandboxPolicy,
)
from fabrica.features.agent_runtime.application.ports import (
    SkillScriptExecutionError,
    SkillScriptExecutor,
)
from fabrica.features.agent_runtime.application.use_cases.evaluate_skill_script_policy import (
    EvaluateSkillScriptPolicy,
)


class ExecuteSkillScript:
    """Execute a selected script only after script policy approval."""

    def __init__(
        self,
        policy_evaluator: EvaluateSkillScriptPolicy,
        executor: SkillScriptExecutor,
    ) -> None:
        self._policy_evaluator = policy_evaluator
        self._executor = executor

    def execute(self, command: SkillScriptExecutionCommand) -> SkillScriptExecutionResult:
        """Evaluate policy and execute only when the selected script is approved."""
        policy_result = self._policy_evaluator.evaluate(
            SkillScriptPolicyEvaluationCommand(
                selection=command.selection,
                sandbox_policy=command.sandbox_policy,
            ),
        )
        if not policy_result.approved or policy_result.binding is None:
            return self._policy_denied_result(command.selection, command.sandbox_policy, policy_result)

        try:
            return self._executor.execute(command, policy_result.binding)
        except SkillScriptExecutionError as err:
            return SkillScriptExecutionResult(
                status=SkillScriptExecutionStatus.ADAPTER_ERROR,
                selection=command.selection,
                binding=policy_result.binding,
                observations=(
                    SkillScriptExecutionObservation(
                        message="script execution adapter failed",
                        metadata={
                            "skill_id": command.selection.skill_id,
                            "script_id": command.selection.script_id,
                            "category": err.category,
                        },
                    ),
                ),
            )

    @staticmethod
    def _policy_denied_result(
        selection: SelectedSkillScript,
        sandbox_policy: SkillScriptSandboxPolicy,
        policy_result: SkillScriptPolicyEvaluationResult,
    ) -> SkillScriptExecutionResult:
        return SkillScriptExecutionResult(
            status=SkillScriptExecutionStatus.POLICY_DENIED,
            selection=selection,
            binding=policy_result.binding,
            observations=(
                SkillScriptExecutionObservation(
                    message="selected script execution was denied by policy",
                    metadata={
                        "skill_id": selection.skill_id,
                        "script_id": selection.script_id,
                        "category": "policy_not_approved",
                        "policy_status": policy_result.status.value,
                        "timeout_seconds": sandbox_policy.timeout_seconds,
                    },
                ),
            ),
        )
