"""Root module entrypoint for the Fabrica product CLI."""

from __future__ import annotations

from fabrica.bootstrap.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
