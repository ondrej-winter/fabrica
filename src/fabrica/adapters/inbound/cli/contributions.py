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
    command_types: tuple[type[object], ...]
    register_commands: CommandRegistrar
    run_command: ContributionRunner

    def can_handle(self, command: object) -> bool:
        """Return whether this contribution owns the parsed command."""
        return isinstance(command, self.command_types)


def validate_cli_contributions(contributions: Sequence[CliContribution]) -> None:
    """Validate that CLI command ownership is explicit and unambiguous."""
    names_by_contribution: dict[str, str] = {}
    owners_by_command_type: dict[type[object], str] = {}
    for contribution in contributions:
        if contribution.name in names_by_contribution:
            msg = f"duplicate CLI contribution name registered: {contribution.name}"
            raise ValueError(msg)
        names_by_contribution[contribution.name] = contribution.name

        for command_type in contribution.command_types:
            if command_type in owners_by_command_type:
                msg = (
                    "duplicate CLI command type ownership registered: "
                    f"{command_type.__name__} owned by "
                    f"{owners_by_command_type[command_type]} and {contribution.name}"
                )
                raise ValueError(msg)
            owners_by_command_type[command_type] = contribution.name
