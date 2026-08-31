"""Tests for host-filtered command environment construction."""

import pytest

from fabrica.features.workspace_command_execution.adapters.outbound.environment import FilteredCommandEnvironmentBuilder
from fabrica.features.workspace_command_execution.application.dtos import CommandErrorCode
from fabrica.features.workspace_command_execution.application.errors import CommandPlanningError


def test_filters_parent_environment_and_applies_authorized_command_override_without_mutation() -> None:
    inherited = {"PATH": "/bin", "SECRET": "not-passed"}
    builder = FilteredCommandEnvironmentBuilder({"PATH": inherited["PATH"]}, frozenset({"CI", "PATH"}))

    environment = builder.build_environment({"CI": "1", "PATH": "/custom/bin"})

    assert environment == {"PATH": "/custom/bin", "CI": "1"}
    assert inherited == {"PATH": "/bin", "SECRET": "not-passed"}
    assert dict(builder.inherited_environment) == {"PATH": "/bin"}


def test_rejects_unauthorized_environment_overrides() -> None:
    builder = FilteredCommandEnvironmentBuilder({"PATH": "/bin"}, frozenset({"CI"}))

    with pytest.raises(CommandPlanningError) as raised:
        builder.build_environment({"TOKEN": "secret"})

    assert raised.value.code is CommandErrorCode.PERMISSION_DENIED
