"""Public contracts shared by feature CLI registrations and the product CLI shell."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import argparse


class CliSubparsers(Protocol):
    """Public behavior needed to register feature-owned CLI commands."""

    def add_parser(self, name: str, **kwargs: object) -> argparse.ArgumentParser:
        """Add one named subcommand parser to the product CLI."""


class CliError(Exception):
    """Base class for expected product CLI boundary failures."""


class CliConfigurationError(CliError):
    """Raised when CLI registration or composition is invalid."""


class CliDispatchError(CliError):
    """Raised when a parsed command cannot be dispatched safely."""


__all__ = [
    "CliConfigurationError",
    "CliDispatchError",
    "CliError",
    "CliSubparsers",
]
