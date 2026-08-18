"""Argparse-backed command registration for the product CLI shell."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fabrica.adapters.inbound.cli.command import Command, RegistrationError
from fabrica.adapters.inbound.cli.destinations import RESERVED_DESTS

_ABSENT_DEFAULT = object()

type AddSubcommandParser = Callable[..., "argparse.ArgumentParser"]


@dataclass(frozen=True, slots=True)
class ParserNamespaceSnapshot:
    """Argparse parser namespace state owned by the shell before feature configuration."""

    action_count: int
    defaults: dict[str, object]


class ArgparseCommandRegistry:
    """Argparse-backed implementation of the command registry.

    The registry keeps the shell's parser state and the feature ``Command``
    objects together. It validates that feature-owned arguments do not overwrite
    shell-reserved destinations.
    """

    def __init__(self, add_parser: AddSubcommandParser) -> None:
        self.add_parser = add_parser
        self.registrations: dict[str, Command[object]] = {}

    def register[TCommand](self, command: Command[TCommand]) -> None:
        """Add one named subcommand parser with typed decoding and execution."""
        if command.name in self.registrations:
            msg = f"CLI command {command.name!r} is already registered"
            raise RegistrationError(msg)
        parser = self.add_parser(
            command.name,
            help=command.summary,
            description=command.description,
        )
        shell_namespace = parser_namespace_snapshot(parser)
        command.configure(parser)
        self.reject_reserved_namespace_mutations(parser, command_name=command.name, shell_namespace=shell_namespace)
        self.registrations[command.name] = cast("Command[object]", command)

    def registration_for(self, command_name: str) -> Command[object]:
        """Return the command definition bound to one parsed command name."""
        try:
            return self.registrations[command_name]
        except KeyError as err:
            msg = f"CLI command {command_name!r} is not registered"
            raise RegistrationError(msg) from err

    def reject_reserved_namespace_mutations(
        self,
        parser: argparse.ArgumentParser,
        *,
        command_name: str,
        shell_namespace: ParserNamespaceSnapshot,
    ) -> None:
        """Reject feature-owned parser state that mutates shell-reserved destinations."""
        self.reject_reserved_dests(parser, command_name=command_name, shell_namespace=shell_namespace)
        self.reject_reserved_default_dests(parser, command_name=command_name, shell_namespace=shell_namespace)

    def reject_reserved_dests(
        self,
        parser: argparse.ArgumentParser,
        *,
        command_name: str,
        shell_namespace: ParserNamespaceSnapshot,
    ) -> None:
        """Reject feature-owned parser actions that use shell-reserved destinations."""
        collisions = sorted(
            action.dest
            for action in feature_owned_actions(parser, shell_namespace=shell_namespace)
            if action.dest in RESERVED_DESTS
        )
        collisions.extend(descendant_reserved_action_dests(parser))
        if collisions:
            joined_collisions = ", ".join(collisions)
            msg = f"CLI command {command_name!r} uses reserved parser destination(s): {joined_collisions}"
            raise RegistrationError(msg)

    def reject_reserved_default_dests(
        self,
        parser: argparse.ArgumentParser,
        *,
        command_name: str,
        shell_namespace: ParserNamespaceSnapshot,
    ) -> None:
        """Reject feature-owned parser defaults reserved by the shell."""
        collisions = sorted(
            dest
            for dest, value in explicit_parser_defaults(parser).items()
            if dest in RESERVED_DESTS and shell_namespace.defaults.get(dest, _ABSENT_DEFAULT) != value
        )
        collisions.extend(descendant_reserved_default_dests(parser))
        if collisions:
            joined_collisions = ", ".join(collisions)
            msg = f"CLI command {command_name!r} uses reserved parser default destination(s): {joined_collisions}"
            raise RegistrationError(msg)


def parser_namespace_snapshot(parser: argparse.ArgumentParser) -> ParserNamespaceSnapshot:
    """Capture parser namespace state before feature-owned configuration runs."""
    return ParserNamespaceSnapshot(action_count=len(parser_actions(parser)), defaults=explicit_parser_defaults(parser))


def feature_owned_actions(
    parser: argparse.ArgumentParser,
    *,
    shell_namespace: ParserNamespaceSnapshot,
) -> list[argparse.Action]:
    """Return parser actions added after the shell-owned namespace snapshot."""
    return parser_actions(parser)[shell_namespace.action_count :]


def parser_actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    """Return parser actions while localizing unavoidable argparse private-state access."""
    return list(parser._actions)  # noqa: SLF001


def explicit_parser_defaults(parser: argparse.ArgumentParser) -> dict[str, object]:
    """Return explicit parser defaults while localizing unavoidable argparse private-state access."""
    return dict(parser._defaults)  # noqa: SLF001


def descendant_reserved_action_dests(parser: argparse.ArgumentParser) -> list[str]:
    """Return reserved destinations used by nested feature-owned parsers."""
    return sorted(
        action.dest
        for descendant in descendant_parsers(parser)
        for action in parser_actions(descendant)
        if action.dest in RESERVED_DESTS
    )


def descendant_reserved_default_dests(parser: argparse.ArgumentParser) -> list[str]:
    """Return reserved defaults used by nested feature-owned parsers."""
    return sorted(
        dest
        for descendant in descendant_parsers(parser)
        for dest in explicit_parser_defaults(descendant)
        if dest in RESERVED_DESTS
    )


def descendant_parsers(parser: argparse.ArgumentParser) -> list[argparse.ArgumentParser]:
    """Return nested parsers reachable from feature-owned subparser actions."""
    descendants: list[argparse.ArgumentParser] = []
    for action in parser_actions(parser):
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            for choice in choices.values():
                if isinstance(choice, argparse.ArgumentParser):
                    descendants.append(choice)
                    descendants.extend(descendant_parsers(choice))
    return descendants
