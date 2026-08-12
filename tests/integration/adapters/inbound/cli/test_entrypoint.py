"""Offline integration tests for the Fabrica product CLI entrypoints."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

EXPECTED_POLICY_DENIED_EXIT_CODE = 5


def test_root_module_entrypoint_help_is_offline_and_lists_explicit_script_execution_command() -> None:
    result = _run_module_entrypoint("--help")

    _assert_help_result(result)


def test_console_script_help_is_offline_and_lists_explicit_script_execution_command() -> None:
    result = _run_console_script("--help")

    _assert_help_result(result)


def test_root_module_entrypoint_dispatches_script_policy_through_bootstrap_without_execution(tmp_path: Path) -> None:
    _write_script(tmp_path, "python-testing", "scripts/check.py", "print('not executed by process smoke')\n")

    result = _run_module_entrypoint(
        "script-policy",
        "--skill-id",
        "python-testing",
        "--script-id",
        "scripts/check.py",
        "--skill-root",
        str(tmp_path),
    )

    _assert_denied_policy_result(result)


def test_console_script_dispatches_script_policy_through_bootstrap_without_execution(tmp_path: Path) -> None:
    _write_script(tmp_path, "python-testing", "scripts/check.py", "print('not executed by process smoke')\n")

    result = _run_console_script(
        "script-policy",
        "--skill-id",
        "python-testing",
        "--script-id",
        "scripts/check.py",
        "--skill-root",
        str(tmp_path),
    )

    _assert_denied_policy_result(result)


def _run_module_entrypoint(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "fabrica", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _run_console_script(*args: str) -> subprocess.CompletedProcess[str]:
    fabrica = shutil.which("fabrica")

    assert fabrica is not None

    return subprocess.run(  # noqa: S603
        [fabrica, *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_help_result(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0
    assert "run" in result.stdout
    assert "commit" in result.stdout
    assert "commit-message" in result.stdout
    assert "script-policy" in result.stdout
    assert "script-execute" in result.stdout
    assert result.stderr == ""


def _assert_denied_policy_result(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == EXPECTED_POLICY_DENIED_EXIT_CODE
    assert result.stdout == ""
    assert "status: denied\n" in result.stderr
    assert "approval_not_approved" in result.stderr
    assert "not executed by process smoke" not in result.stderr


def _write_script(root: Path, skill_id: str, script_id: str, text: str) -> Path:
    script_file = root / skill_id / script_id
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(text, encoding="utf-8")
    return script_file
