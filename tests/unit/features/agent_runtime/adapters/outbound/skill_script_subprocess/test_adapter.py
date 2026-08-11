"""Tests for constrained local Agent Skill script subprocess execution."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from fabrica.features.agent_runtime.adapters.outbound.skill_script_file import SkillScriptFileMetadataLoader
from fabrica.features.agent_runtime.adapters.outbound.skill_script_subprocess import (
    SkillScriptSubprocessExecutionSettings,
    SkillScriptSubprocessExecutor,
)
from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptExecutionCommand,
    SkillScriptExecutionStatus,
    SkillScriptSandboxPolicy,
    SkillScriptType,
)

EXPECTED_NON_ZERO_EXIT_CODE = 7
SHORT_OUTPUT_BOUND = 3


def test_execute_runs_approved_python_script_and_captures_stdout(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "python-testing", "scripts/check.py", "print('hello from script')\n")
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)

    result = _executor(tmp_path).execute(
        SkillScriptExecutionCommand(selection=selection),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.SUCCESS
    assert result.exit_code == 0
    assert result.stdout.text == "hello from script\n"
    assert result.stderr.text == ""
    assert result.binding == binding
    assert result.observations[0].metadata["category"] == "executed"


def test_execute_runs_approved_shell_script_through_explicit_interpreter(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "shell-testing", "scripts/check.sh", "echo shell-ok\n")
    selection = SelectedSkillScript(skill_id="shell-testing", script_id="scripts/check.sh")
    binding = _binding(selection, script, SkillScriptType.SHELL)

    result = _executor(tmp_path, shell_interpreter="/bin/sh").execute(
        SkillScriptExecutionCommand(selection=selection),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.SUCCESS
    assert result.stdout.text == "shell-ok\n"
    assert result.observations[0].metadata["category"] == "executed"


def test_execute_refuses_mismatched_binding_without_running_script(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "python-testing",
        "scripts/check.py",
        "from pathlib import Path\nPath('created.txt').write_text('ran', encoding='utf-8')\n",
    )
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/check.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON, content_digest="sha256:not-current")
    working_directory = tmp_path / "work"

    result = _executor(tmp_path, working_directory=working_directory).execute(
        SkillScriptExecutionCommand(selection=selection),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.ADAPTER_ERROR
    assert result.observations[0].metadata["category"] == "binding_mismatch"
    assert not (working_directory / "created.txt").exists()


def test_execute_maps_non_zero_exit_to_execution_failed(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "python-testing",
        "scripts/fail.py",
        "import sys\nprint('bad', file=sys.stderr)\nsys.exit(7)\n",
    )
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/fail.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)

    result = _executor(tmp_path).execute(
        SkillScriptExecutionCommand(selection=selection),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.EXECUTION_FAILED
    assert result.exit_code == EXPECTED_NON_ZERO_EXIT_CODE
    assert result.stderr.text == "bad\n"
    assert result.observations[0].metadata["category"] == "non_zero_exit"


def test_execute_maps_timeout_to_timed_out(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "python-testing", "scripts/sleep.py", "import time\ntime.sleep(2)\n")
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/sleep.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)

    result = _executor(tmp_path).execute(
        SkillScriptExecutionCommand(
            selection=selection,
            sandbox_policy=SkillScriptSandboxPolicy(timeout_seconds=1),
        ),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.TIMED_OUT
    assert result.exit_code is None
    assert result.observations[0].metadata["category"] == "timed_out"


def test_execute_bounds_stdout_and_records_truncation(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "python-testing", "scripts/output.py", "print('abcdef', end='')\n")
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/output.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)

    result = _executor(tmp_path).execute(
        SkillScriptExecutionCommand(
            selection=selection,
            sandbox_policy=SkillScriptSandboxPolicy(max_stdout_chars=SHORT_OUTPUT_BOUND),
        ),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.SUCCESS
    assert result.stdout.text == "abc"
    assert result.stdout.truncated is True
    assert result.stdout.max_chars == SHORT_OUTPUT_BOUND


def test_execute_uses_empty_environment_by_default(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "python-testing",
        "scripts/env.py",
        "import os\nprint(os.environ.get('PATH', '<missing>'))\n",
    )
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/env.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)

    result = _executor(tmp_path).execute(
        SkillScriptExecutionCommand(selection=selection),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.SUCCESS
    assert result.stdout.text == "<missing>\n"


def test_execute_uses_explicit_working_directory_for_script_writes(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "python-testing",
        "scripts/write.py",
        "from pathlib import Path\nPath('created.txt').write_text('ok', encoding='utf-8')\n",
    )
    working_directory = tmp_path / "work"
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/write.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)

    result = _executor(tmp_path, working_directory=working_directory).execute(
        SkillScriptExecutionCommand(selection=selection),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.SUCCESS
    assert (working_directory / "created.txt").read_text(encoding="utf-8") == "ok"
    assert not (Path.cwd() / "created.txt").exists()


def test_execute_uses_temporary_working_directory_by_default(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "python-testing",
        "scripts/pwd.py",
        "from pathlib import Path\nPath('created.txt').write_text('ok', encoding='utf-8')\nprint(Path.cwd())\n",
    )
    selection = SelectedSkillScript(skill_id="python-testing", script_id="scripts/pwd.py")
    binding = _binding(selection, script, SkillScriptType.PYTHON)

    result = _executor(tmp_path).execute(
        SkillScriptExecutionCommand(selection=selection),
        binding,
    )

    execution_cwd = Path(result.stdout.text.strip())
    assert result.status is SkillScriptExecutionStatus.SUCCESS
    assert execution_cwd != Path.cwd()
    assert not execution_cwd.exists()
    assert not (Path.cwd() / "created.txt").exists()


def test_execute_returns_unsupported_for_missing_shell_interpreter(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "shell-testing", "scripts/check.sh", "echo nope\n")
    selection = SelectedSkillScript(skill_id="shell-testing", script_id="scripts/check.sh")
    binding = _binding(selection, script, SkillScriptType.SHELL)

    result = _executor(tmp_path, shell_interpreter=tmp_path / "missing-sh").execute(
        SkillScriptExecutionCommand(selection=selection),
        binding,
    )

    assert result.status is SkillScriptExecutionStatus.UNSUPPORTED
    assert result.observations[0].metadata["category"] == "missing_interpreter"


def test_constructing_executor_does_not_read_skill_roots_or_run_scripts(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-skills"

    executor = _executor(missing_root)

    assert executor is not None
    assert not missing_root.exists()


def _write_script(root: Path, skill_id: str, script_id: str, text: str) -> Path:
    script_file = root / skill_id / script_id
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(text, encoding="utf-8")
    return script_file


def _executor(
    skill_root: Path,
    *,
    shell_interpreter: str | Path = "/bin/sh",
    working_directory: Path | None = None,
) -> SkillScriptSubprocessExecutor:
    return SkillScriptSubprocessExecutor(
        metadata_loader=SkillScriptFileMetadataLoader(skill_roots=(skill_root,)),
        skill_roots=(skill_root,),
        settings=SkillScriptSubprocessExecutionSettings(
            shell_interpreter=shell_interpreter,
            working_directory=working_directory,
        ),
    )


def _binding(
    selection: SelectedSkillScript,
    script_file: Path,
    script_type: SkillScriptType,
    *,
    content_digest: str | None = None,
) -> SkillScriptApprovalBinding:
    script_bytes = script_file.read_bytes()
    return SkillScriptApprovalBinding(
        skill_id=selection.skill_id,
        script_id=selection.script_id,
        script_type=script_type,
        suffix=script_file.suffix,
        byte_size=len(script_bytes),
        content_digest=content_digest or f"sha256:{sha256(script_bytes).hexdigest()}",
    )
