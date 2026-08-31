"""Tests for workspace-command-execution application port ownership."""

import inspect
from datetime import UTC, datetime

import pytest

from fabrica.features.workspace_command_execution.application import ports
from fabrica.features.workspace_command_execution.application.dtos import CommandExecutionLimits
from fabrica.features.workspace_command_execution.application.ports import RunCommandsContext


class NeverCancelled:
    """Cancellation signal that never requests cancellation."""

    @property
    def is_cancelled(self) -> bool:
        """Return that the test batch remains active."""
        return False


def test_ports_are_application_owned_without_adapter_or_subprocess_dependencies() -> None:
    exported_names = set(ports.__all__)

    assert {
        "CommandApprovalResolver",
        "CommandCancellationSignal",
        "CommandEnvironmentBuilder",
        "CommandPermissionDecision",
        "CommandPermissionEvaluator",
        "CommandProgressReporter",
        "CommandSandboxPreflight",
        "CommandSupervisor",
        "CommandWorkspaceResolver",
        "RunCommandsContext",
    } <= exported_names
    source = inspect.getsource(ports)
    assert ".adapters" not in source
    assert "subprocess" not in source


def test_context_requires_an_aware_deadline() -> None:
    naive_deadline = datetime.fromtimestamp(0, tz=UTC).replace(tzinfo=None)

    with pytest.raises(ValueError, match="timezone-aware"):
        RunCommandsContext(NeverCancelled(), CommandExecutionLimits(), naive_deadline)
