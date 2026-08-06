"""Shared product CLI option DTOs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CliGlobalOptions:
    """Parsed CLI options shared by all subcommands."""

    print_usage: bool = False
    print_prices: bool = False
    verbose_diagnostics: bool = False
