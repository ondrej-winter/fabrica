"""Contribution contracts for the product CLI shell."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    import argparse

    from fabrica.adapters.inbound.cli.options import CliGlobalOptions


class CliSubparsers(Protocol):
    """Public behavior needed to register feature-owned CLI commands."""

    def add_parser(self, name: str, **kwargs: object) -> argparse.ArgumentParser:
        """Add one named subcommand parser to the product CLI."""


type CommandRegistrar = Callable[[CliSubparsers], None]
type ContributionRunner = Callable[[object, "CliExecutionContext"], int]


class CliError(Exception):
    """Base class for expected product CLI boundary failures."""


class CliConfigurationError(CliError):
    """Raised when CLI registration or composition is invalid."""


class CliDispatchError(CliError):
    """Raised when a parsed command cannot be dispatched safely."""


@dataclass(frozen=True, slots=True)
class CliExecutionContext:
    """Shared execution context passed from the product CLI shell to one contribution."""

    global_options: CliGlobalOptions
    composition_options: object | None
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


@dataclass(frozen=True, slots=True)
class CliContribution:
    """One feature-owned command contribution aggregated by the product CLI."""

    name: str
    command_names: tuple[str, ...]
    command_types: tuple[type[object], ...]
    register_commands: CommandRegistrar
    run_command: ContributionRunner

    def can_handle(self, command: object) -> bool:
        """Return whether this contribution owns the parsed command."""
        return isinstance(command, self.command_types)


def validate_cli_contributions(contributions: Sequence[CliContribution]) -> None:
    """Validate that CLI command ownership is explicit and unambiguous."""
    names_by_contribution: dict[str, str] = {}
    owners_by_command_name: dict[str, str] = {}
    owners_by_command_type: dict[type[object], str] = {}
    for contribution in contributions:
        if contribution.name in names_by_contribution:
            msg = f"duplicate CLI contribution name registered: {contribution.name}"
            raise CliConfigurationError(msg)
        names_by_contribution[contribution.name] = contribution.name

        for command_name in contribution.command_names:
            if command_name in owners_by_command_name:
                msg = (
                    "duplicate CLI subcommand name registered: "
                    f"{command_name} owned by {owners_by_command_name[command_name]} and {contribution.name}"
                )
                raise CliConfigurationError(msg)
            owners_by_command_name[command_name] = contribution.name

        for command_type in contribution.command_types:
            if command_type in owners_by_command_type:
                msg = (
                    "duplicate CLI command type ownership registered: "
                    f"{command_type.__name__} owned by "
                    f"{owners_by_command_type[command_type]} and {contribution.name}"
                )
                raise CliConfigurationError(msg)
            overlapping_owner = _overlapping_command_owner(
                command_type,
                owners_by_command_type=owners_by_command_type,
            )
            if overlapping_owner is not None:
                owned_type, owner = overlapping_owner
                msg = (
                    "overlapping CLI command type ownership registered: "
                    f"{command_type.__name__} owned by {contribution.name} overlaps with "
                    f"{owned_type.__name__} owned by {owner}"
                )
                raise CliConfigurationError(msg)
            owners_by_command_type[command_type] = contribution.name


def _overlapping_command_owner(
    command_type: type[object],
    *,
    owners_by_command_type: dict[type[object], str],
) -> tuple[type[object], str] | None:
    for owned_type, owner in owners_by_command_type.items():
        if issubclass(command_type, owned_type) or issubclass(owned_type, command_type):
            return owned_type, owner
    return None
