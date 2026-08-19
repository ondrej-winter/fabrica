"""Tests for the local agent runtime CLI script-policy command."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from typing import TYPE_CHECKING, TextIO

import fabrica.bootstrap.cli.features.agent_runtime as agent_runtime_bootstrap
from fabrica.bootstrap.cli import run_cli
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import CliScriptPolicyCommand
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import AgentRuntimeCliStreams
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import run_script_policy_cli_command
from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyEvaluationResult,
    SkillScriptPolicyStatus,
    SkillScriptType,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

EXPECTED_METADATA_ERROR_EXIT_CODE = 2
EXPECTED_UNSUPPORTED_EXIT_CODE = 4
EXPECTED_POLICY_DENIED_EXIT_CODE = 5


def run_feature_cli_command(
    command: CliScriptPolicyCommand,
    *,
    evaluator: FakeScriptPolicyEvaluator,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    return run_script_policy_cli_command(
        command,
        streams=AgentRuntimeCliStreams(stdout=stdout or StringIO(), stderr=stderr or StringIO()),
        evaluator=evaluator,
    )


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

    exit_code = run_feature_cli_command(
        CliScriptPolicyCommand(skill_id="python-testing", script_id="scripts/check.py"),
        evaluator=evaluator,
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

    exit_code = run_feature_cli_command(
        CliScriptPolicyCommand(skill_id="python-testing", script_id="scripts/check.py"),
        evaluator=evaluator,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == (
        "status: approved\n"
        "approve-script-type: python\n"
        "approve-suffix: .py\n"
        "approve-byte-size: 128\n"
        "approve-content-digest: sha256:abc123\n"
    )
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

        exit_code = run_feature_cli_command(
            CliScriptPolicyCommand(skill_id="python-testing", script_id="scripts/check.py"),
            evaluator=evaluator,
            stdout=StringIO(),
            stderr=StringIO(),
        )

        assert exit_code == expected_exit_code


def test_script_policy_command_default_composition_denies_synthetic_script_without_execution(tmp_path: Path) -> None:
    _write_script(tmp_path, "python-testing", "scripts/check.py", "print('not executed by policy inspection')\n")
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        (
            "script-policy",
            "--skill-id",
            "python-testing",
            "--script-id",
            "scripts/check.py",
            "--skill-root",
            str(tmp_path),
        ),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_POLICY_DENIED_EXIT_CODE
    assert stdout.getvalue() == ""
    assert "status: denied\n" in stderr.getvalue()
    assert "approval_not_approved" in stderr.getvalue()
    assert "not executed by policy inspection" not in stderr.getvalue()


def test_script_policy_default_composition_does_not_create_codex_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_runtime_is_created() -> object:
        msg = "script-policy must not create the Codex runtime"
        raise AssertionError(msg)

    monkeypatch.setattr(agent_runtime_bootstrap, "_create_default_runtime", fail_if_runtime_is_created)
    _write_script(tmp_path, "python-testing", "scripts/check.py", "print('not executed by policy inspection')\n")

    exit_code = run_cli(
        (
            "script-policy",
            "--skill-id",
            "python-testing",
            "--script-id",
            "scripts/check.py",
            "--skill-root",
            str(tmp_path),
        ),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == EXPECTED_POLICY_DENIED_EXIT_CODE


def test_script_policy_invocation_passes_composition_skill_roots_to_default_composition(tmp_path: Path) -> None:
    _write_script(tmp_path, "python-testing", "scripts/check.py", "print('not executed by policy inspection')\n")
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        (
            "script-policy",
            "--skill-id",
            "python-testing",
            "--script-id",
            "scripts/check.py",
            "--skill-root",
            str(tmp_path),
        ),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_POLICY_DENIED_EXIT_CODE
    assert stdout.getvalue() == ""
    assert "status: denied\n" in stderr.getvalue()


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


def _write_script(root: Path, skill_id: str, script_id: str, text: str) -> Path:
    script_file = root / skill_id / script_id
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(text, encoding="utf-8")
    return script_file
