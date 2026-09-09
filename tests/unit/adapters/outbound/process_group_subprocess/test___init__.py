"""Tests for the process-group subprocess package API."""

from fabrica.adapters.outbound import process_group_subprocess
from fabrica.adapters.outbound.process_group_subprocess import command, contracts


def test_exports_supported_process_group_subprocess_api() -> None:
    assert process_group_subprocess.__all__ == [
        "DEFAULT_TERMINATION_GRACE_SECONDS",
        "ProcessGroupCommandResult",
        "ProcessGroupCommandSettings",
        "run_process_group_command",
    ]
    assert process_group_subprocess.DEFAULT_TERMINATION_GRACE_SECONDS is contracts.DEFAULT_TERMINATION_GRACE_SECONDS
    assert process_group_subprocess.ProcessGroupCommandResult is contracts.ProcessGroupCommandResult
    assert process_group_subprocess.ProcessGroupCommandSettings is contracts.ProcessGroupCommandSettings
    assert process_group_subprocess.run_process_group_command is command.run_process_group_command
