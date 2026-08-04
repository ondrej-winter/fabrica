"""Offline integration tests for the local agent runtime CLI entrypoint."""

from __future__ import annotations

import shutil
import subprocess
import sys


def test_module_entrypoint_help_is_offline_and_lists_explicit_script_execution_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "fabrica.features.agent_runtime.adapters.inbound.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run" in result.stdout
    assert "commit-message" in result.stdout
    assert "script-policy" in result.stdout
    assert "script-execute" in result.stdout
    assert result.stderr == ""


def test_console_script_help_is_offline_and_lists_explicit_script_execution_command() -> None:
    fabrica = shutil.which("fabrica")

    assert fabrica is not None

    result = subprocess.run(  # noqa: S603
        [fabrica, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run" in result.stdout
    assert "commit-message" in result.stdout
    assert "script-policy" in result.stdout
    assert "script-execute" in result.stdout
    assert result.stderr == ""
