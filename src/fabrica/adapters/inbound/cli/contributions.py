"""Contribution contracts for the product CLI shell."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

from fabrica.adapters.inbound.cli.contracts import CliConfigurationError, CliSubparsers

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.options import CliGlobalOptions

type CommandRegistrar = Callable[[CliSubparsers], None]
type ContributionRunner[TCommand] = Callable[[TCommand, "CliExecutionContext"], int]


@dataclass(frozen=True, slots=True)
class CliExecutionContext:
    """Shared execution context passed from the product CLI shell to one contribution."""

    global_options: CliGlobalOptions
    composition_options: object | None
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


@dataclass(frozen=True, slots=True)
class CliContribution[TCommand]:
    """One feature-owned command contribution aggregated by the product CLI."""

    name: str
    command_names: tuple[str, ...]
    command_types: tuple[type[TCommand], ...]
    register_commands: CommandRegistrar
    run_command: ContributionRunner[TCommand]

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


def resolve_composition_options[TOptions](
    context: CliExecutionContext,
    options_type: type[TOptions],
    *,
    contribution_name: str,
    default_factory: Callable[[], TOptions],
) -> TOptions:
    """Return typed composition options for one contribution execution context."""
    if context.composition_options is None:
        return default_factory()
    if not isinstance(context.composition_options, options_type):
        msg = (
            f"{contribution_name} CLI contribution received incompatible composition options: "
            f"{type(context.composition_options).__name__}"
        )
        raise CliConfigurationError(msg)
    return context.composition_options


def _overlapping_command_owner(
    command_type: type[object],
    *,
    owners_by_command_type: dict[type[object], str],
) -> tuple[type[object], str] | None:
    for owned_type, owner in owners_by_command_type.items():
        if issubclass(command_type, owned_type) or issubclass(owned_type, command_type):
            return owned_type, owner
    return None
