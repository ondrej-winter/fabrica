"""Argparse-backed command registration for the product CLI adapter."""

from __future__ import annotations

import argparse
from typing import Any, cast

from fabrica.adapters.inbound.cli.command import Command, RegistrationError
from fabrica.adapters.inbound.cli.destinations import RESERVED_DESTS
from fabrica.adapters.inbound.cli.options import add_global_options


class ArgparseCommandRegistry:
    """Argparse-backed implementation of the command registry."""

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
        add_global_options(parser, default=argparse.SUPPRESS)
        shell_dest_count = len(parser._actions)  # noqa: SLF001
        command.configure(parser)
        self.reject_reserved_dests(parser, command_name=command.name, shell_dest_count=shell_dest_count)
        self.registrations[command.name] = cast("Command[object]", command)

    def registration_for(self, command_name: str) -> Command[object]:
        """Return the registration bound to one parsed command name."""
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
        """Reject feature-owned parser destinations reserved by the product CLI."""
        collisions = sorted(
            action.dest
            for action in parser._actions[shell_dest_count:]  # noqa: SLF001
            if action.dest in RESERVED_DESTS
        )
        if collisions:
            joined_collisions = ", ".join(collisions)
            msg = f"CLI command {command_name!r} uses reserved parser destination(s): {joined_collisions}"
            raise RegistrationError(msg)
