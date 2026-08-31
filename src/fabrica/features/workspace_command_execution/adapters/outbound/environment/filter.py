"""Filtered, immutable-parent environment construction for command children."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fabrica.features.workspace_command_execution.application.dtos import CommandErrorCode
from fabrica.features.workspace_command_execution.application.errors import CommandPlanningError


@dataclass(frozen=True, slots=True)
class FilteredCommandEnvironmentBuilder:
    """Apply explicit host inheritance and override-key policy to one command."""

    inherited_environment: Mapping[str, str]
    allowed_override_keys: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inherited_environment", MappingProxyType(dict(self.inherited_environment)))

    def build_environment(self, requested_overrides: dict[str, str]) -> dict[str, str]:
        """Build a child-only environment without mutating the host environment."""
        unauthorized = set(requested_overrides).difference(self.allowed_override_keys)
        if unauthorized:
            raise CommandPlanningError(CommandErrorCode.PERMISSION_DENIED, "environment override was not permitted")
        environment = dict(self.inherited_environment)
        environment.update(requested_overrides)
        return environment
