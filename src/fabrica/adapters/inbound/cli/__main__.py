"""Module entrypoint for the Fabrica product CLI shell."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.bootstrap.cli import main as _bootstrap_main

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Fabrica CLI and return a process exit code."""
    return _bootstrap_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
