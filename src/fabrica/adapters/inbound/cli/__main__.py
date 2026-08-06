"""Module and console-script entrypoint for the local agent runtime CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.parser import parse_args
from fabrica.adapters.inbound.cli.runner import run_cli_command

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local agent runtime CLI and return a process exit code."""
    invocation = parse_args(tuple(argv) if argv is not None else None)
    return run_cli_command(invocation)


if __name__ == "__main__":
    raise SystemExit(main())
