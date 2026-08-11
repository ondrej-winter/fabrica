"""Tests for the local agent runtime CLI script-execute command."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
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
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import CliScriptExecuteCommand
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import AgentRuntimeCliDependencies
from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptExecutionCommand,
    SkillScriptExecutionObservation,
    SkillScriptExecutionOutput,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptType,
)

EXPECTED_POLICY_DENIED_EXIT_CODE = 5
EXPECTED_EXECUTION_FAILED_EXIT_CODE = 6
EXPECTED_TIMED_OUT_EXIT_CODE = 7


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
class FakeScriptExecutor:
    """Test double for selected skill script execution."""

    result: SkillScriptExecutionResult
    calls: list[SkillScriptExecutionCommand] = field(default_factory=list)

    def execute(self, command: SkillScriptExecutionCommand) -> SkillScriptExecutionResult:
        self.calls.append(command)
        return self.result


def test_script_execute_command_maps_explicit_selection_to_executor() -> None:
    executor = FakeScriptExecutor(
        result=SkillScriptExecutionResult(
            status=SkillScriptExecutionStatus.SUCCESS,
            selection=_selection(),
            stdout=SkillScriptExecutionOutput(text="script-ok\n"),
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        _command(),
        dependencies=AgentRuntimeCliDependencies(script_executor=executor),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "script-ok\nstatus: success\n"
    assert stderr.getvalue() == ""
    assert executor.calls == [SkillScriptExecutionCommand(selection=_selection())]


def test_script_execute_command_maps_failure_statuses_to_stable_exit_codes() -> None:
    for status, expected_exit_code in (
        (SkillScriptExecutionStatus.POLICY_DENIED, EXPECTED_POLICY_DENIED_EXIT_CODE),
        (SkillScriptExecutionStatus.EXECUTION_FAILED, EXPECTED_EXECUTION_FAILED_EXIT_CODE),
        (SkillScriptExecutionStatus.TIMED_OUT, EXPECTED_TIMED_OUT_EXIT_CODE),
    ):
        executor = FakeScriptExecutor(
            result=SkillScriptExecutionResult(status=status, selection=_selection()),
        )

        exit_code = run_cli_command(
            _command(),
            dependencies=AgentRuntimeCliDependencies(script_executor=executor),
            stdout=StringIO(),
            stderr=StringIO(),
        )

        assert exit_code == expected_exit_code


def test_script_execute_command_writes_bounded_failure_details_to_stderr() -> None:
    executor = FakeScriptExecutor(
        result=SkillScriptExecutionResult(
            status=SkillScriptExecutionStatus.EXECUTION_FAILED,
            selection=_selection(),
            stderr=SkillScriptExecutionOutput(text="bad\n"),
            exit_code=7,
            observations=(
                SkillScriptExecutionObservation(
                    message="selected script exited with a non-zero status",
                    metadata={"category": "non_zero_exit", "script_id": "scripts/check.py"},
                ),
            ),
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        _command(),
        dependencies=AgentRuntimeCliDependencies(script_executor=executor),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_EXECUTION_FAILED_EXIT_CODE
    assert stdout.getvalue() == ""
    assert "bad\n" in stderr.getvalue()
    assert "status: execution_failed\n" in stderr.getvalue()
    assert "exit_code: 7\n" in stderr.getvalue()
    assert "category=non_zero_exit" in stderr.getvalue()


def test_script_execute_default_composition_executes_only_matching_approved_synthetic_script(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "python-testing", "scripts/check.py", "print('cli-execution-ok')\n")
    binding = _binding(_selection(), script)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        _command(
            skill_roots=(tmp_path,),
            approval_byte_size=binding.byte_size,
            approval_content_digest=binding.content_digest,
        ),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == (
        "cli-execution-ok\n"
        "status: success\n"
        "exit_code: 0\n"
        "observation: selected script executed category=executed script_id=scripts/check.py skill_id=python-testing\n"
    )
    assert stderr.getvalue() == ""


def test_script_execute_default_composition_denies_mismatched_approval_without_execution(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "python-testing",
        "scripts/write.py",
        "from pathlib import Path\nPath('created.txt').write_text('ran', encoding='utf-8')\n",
    )
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/write.py")
    binding = _binding(selection, script)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        _command(
            script_id="scripts/write.py",
            skill_roots=(tmp_path,),
            approval_byte_size=binding.byte_size,
            approval_content_digest="sha256:not-current",
        ),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_POLICY_DENIED_EXIT_CODE
    assert stdout.getvalue() == ""
    assert "status: policy_denied\n" in stderr.getvalue()
    assert "policy_not_approved" in stderr.getvalue()
    assert "created.txt" not in stderr.getvalue()
    assert not (Path.cwd() / "created.txt").exists()


def _selection() -> SelectedSkillScript:
    return SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")


def _command(
    *,
    script_id: str = "scripts/check.py",
    skill_roots: tuple[Path, ...] = (),
    approval_byte_size: int = 128,
    approval_content_digest: str = "sha256:abc123",
) -> CliScriptExecuteCommand:
    return CliScriptExecuteCommand(
        skill_id="python-testing",
        script_id=script_id,
        approval_script_type=SkillScriptType.PYTHON,
        approval_suffix=".py",
        approval_byte_size=approval_byte_size,
        approval_content_digest=approval_content_digest,
        skill_roots=skill_roots,
    )


def _write_script(root: Path, skill_id: str, script_id: str, text: str) -> Path:
    script_file = root / skill_id / script_id
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(text, encoding="utf-8")
    return script_file


def _binding(selection: SelectedSkillScript, script: Path) -> SkillScriptApprovalBinding:
    content = script.read_bytes()
    return SkillScriptApprovalBinding(
        skill_id=selection.skill_id,
        script_id=selection.script_id,
        script_type=SkillScriptType.PYTHON,
        suffix=script.suffix,
        byte_size=len(content),
        content_digest=f"sha256:{sha256(content).hexdigest()}",
    )
