"""Tests for process-group subprocess contracts and settings."""

import os

from fabrica.adapters.outbound.process_group_subprocess.contracts import (
    DEFAULT_TERMINATION_GRACE_SECONDS,
    ProcessGroupCommandResult,
    ProcessGroupCommandSettings,
)
from fabrica.adapters.outbound.process_group_subprocess.process import open_process


def test_command_result_defaults_captured_output_to_empty_text() -> None:
    result = ProcessGroupCommandResult(returncode=0)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_command_settings_use_safe_subprocess_defaults() -> None:
    settings = ProcessGroupCommandSettings()

    assert settings.env is None
    assert settings.text is False
    assert settings.termination_grace_seconds == DEFAULT_TERMINATION_GRACE_SECONDS
    assert settings.process_factory is open_process
    assert settings.group_signal_sender is os.killpg
