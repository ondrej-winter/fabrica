"""Tests for the local agent runtime CLI script-policy command."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import TextIO

from fabrica.adapters.inbound.cli import (
    CliCommand,
    CliCommandExecutionOptions,
    CliInvocation,
)
from fabrica.adapters.inbound.cli import (
    run_cli_command as _run_cli_command,
)
from fabrica.bootstrap.cli import create_cli_contributions
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import CliScriptPolicyCommand
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import AgentRuntimeCliDependencies
from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyEvaluationResult,
    SkillScriptPolicyStatus,
    SkillScriptType,
)

EXPECTED_METADATA_ERROR_EXIT_CODE = 2
EXPECTED_UNSUPPORTED_EXIT_CODE = 4
EXPECTED_POLICY_DENIED_EXIT_CODE = 5


def run_cli_command(
    invocation: CliCommand | CliInvocation,
    *,
    dependencies: AgentRuntimeCliDependencies | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    options = CliCommandExecutionOptions(
        contributions=create_cli_contributions(agent_runtime_dependencies=dependencies),
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )
    return _run_cli_command(invocation, options=options)


@dataclass
class FakeScriptPolicyEvaluator:
    """Test double for selected skill script policy evaluation."""

    result: SkillScriptPolicyEvaluationResult
    calls: list[SkillScriptPolicyEvaluationCommand] = field(default_factory=list)

    def evaluate(self, command: SkillScriptPolicyEvaluationCommand) -> SkillScriptPolicyEvaluationResult:
        self.calls.append(command)
        return self.result


def test_script_policy_command_maps_explicit_selection_to_policy_evaluator() -> None:
    evaluator = FakeScriptPolicyEvaluator(
        result=SkillScriptPolicyEvaluationResult(
            status=SkillScriptPolicyStatus.DENIED,
            selection=_selection(),
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        CliScriptPolicyCommand(
            skill_id="python-testing",
            script_id="scripts/check.py",
            skill_roots=(Path("synthetic-skills"),),
        ),
        dependencies=AgentRuntimeCliDependencies(script_policy_evaluator=evaluator),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_POLICY_DENIED_EXIT_CODE
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "status: denied\n"
    assert evaluator.calls == [SkillScriptPolicyEvaluationCommand(selection=_selection())]


def test_script_policy_command_writes_approved_status_to_stdout() -> None:
    binding = _binding()
    evaluator = FakeScriptPolicyEvaluator(
        result=SkillScriptPolicyEvaluationResult(
            status=SkillScriptPolicyStatus.APPROVED,
            selection=_selection(),
            binding=binding,
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        CliScriptPolicyCommand(skill_id="python-testing", script_id="scripts/check.py"),
        dependencies=AgentRuntimeCliDependencies(script_policy_evaluator=evaluator),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "status: approved\n"
    assert stderr.getvalue() == ""


def test_script_policy_command_maps_non_approved_statuses_to_stable_exit_codes() -> None:
    for status, expected_exit_code in (
        (SkillScriptPolicyStatus.DENIED, EXPECTED_POLICY_DENIED_EXIT_CODE),
        (SkillScriptPolicyStatus.POLICY_VIOLATION, EXPECTED_POLICY_DENIED_EXIT_CODE),
        (SkillScriptPolicyStatus.UNSUPPORTED, EXPECTED_UNSUPPORTED_EXIT_CODE),
        (SkillScriptPolicyStatus.METADATA_ERROR, EXPECTED_METADATA_ERROR_EXIT_CODE),
    ):
        evaluator = FakeScriptPolicyEvaluator(
            result=SkillScriptPolicyEvaluationResult(status=status, selection=_selection()),
        )

        exit_code = run_cli_command(
            CliScriptPolicyCommand(skill_id="python-testing", script_id="scripts/check.py"),
            dependencies=AgentRuntimeCliDependencies(script_policy_evaluator=evaluator),
            stdout=StringIO(),
            stderr=StringIO(),
        )

        assert exit_code == expected_exit_code


def test_script_policy_command_default_composition_denies_synthetic_script_without_execution(tmp_path: Path) -> None:
    script_file = tmp_path / "python-testing" / "scripts" / "check.py"
    script_file.parent.mkdir(parents=True)
    script_file.write_text("print('not executed by policy inspection')\n", encoding="utf-8")
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        CliScriptPolicyCommand(
            skill_id="python-testing",
            script_id="scripts/check.py",
            skill_roots=(tmp_path,),
        ),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_POLICY_DENIED_EXIT_CODE
    assert stdout.getvalue() == ""
    assert "status: denied\n" in stderr.getvalue()
    assert "approval_not_approved" in stderr.getvalue()
    assert "not executed by policy inspection" not in stderr.getvalue()


def _selection() -> SelectedSkillScript:
    return SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")


def _binding() -> SkillScriptApprovalBinding:
    return SkillScriptApprovalBinding(
        skill_id="python-testing",
        script_id="scripts/check.py",
        script_type=SkillScriptType.PYTHON,
        suffix=".py",
        byte_size=128,
        content_digest="sha256:abc123",
    )
