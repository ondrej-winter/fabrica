"""Argparse-backed command registration for the product CLI shell."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from fabrica.adapters.inbound.cli.command import Command, RegistrationError
from fabrica.adapters.inbound.cli.destinations import RESERVED_DESTS

if TYPE_CHECKING:
    import argparse


class ArgparseCommandRegistry:
    """Argparse-backed implementation of the command registry.

    The registry keeps the shell's parser state and the feature ``Command``
    objects together. It validates that feature-owned arguments do not overwrite
    shell-reserved destinations.
    """

    def __init__(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        self.subparsers = subparsers
        self.registrations: dict[str, Command[object]] = {}

    def register[TCommand](self, command: Command[TCommand]) -> None:
        """Add one named subcommand parser with typed decoding and execution."""
        if command.name in self.registrations:
            msg = f"CLI command {command.name!r} is already registered"
            raise RegistrationError(msg)
        parser = self.subparsers.add_parser(
            command.name,
            help=command.summary,
            description=command.description,
        )
        shell_dest_count = len(parser._actions)  # noqa: SLF001
        command.configure(parser)
        self.reject_reserved_dests(parser, command_name=command.name, shell_dest_count=shell_dest_count)
        self.registrations[command.name] = cast("Command[object]", command)

    def registration_for(self, command_name: str) -> Command[object]:
        """Return the command definition bound to one parsed command name."""
        try:
            return self.registrations[command_name]
        except KeyError as err:
            msg = f"CLI command {command_name!r} is not registered"
            raise RegistrationError(msg) from err

    def reject_reserved_dests(
        self,
        parser: argparse.ArgumentParser,
        *,
        command_name: str,
        shell_dest_count: int,
    ) -> None:
        """Reject feature-owned parser destinations reserved by the shell.

        ``shell_dest_count`` marks the parser actions created before the feature
        configurer ran. Only later actions are feature-owned and eligible for the
        collision check.
        """
        collisions = sorted(
            action.dest
            for action in parser._actions[shell_dest_count:]  # noqa: SLF001
            if action.dest in RESERVED_DESTS
        )
        if collisions:
            joined_collisions = ", ".join(collisions)
            msg = f"CLI command {command_name!r} uses reserved parser destination(s): {joined_collisions}"
            raise RegistrationError(msg)
