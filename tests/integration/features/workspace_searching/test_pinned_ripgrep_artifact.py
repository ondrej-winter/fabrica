"""Integration checks for the selected local pinned ripgrep package artifact."""

import subprocess
import sys

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import (
    verified_linux_pinned_ripgrep_executable,
)

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux package-data ripgrep conformance")


def test_linux_pinned_ripgrep_executable_reports_the_pinned_release_version() -> None:
    executable = verified_linux_pinned_ripgrep_executable()

    completed = subprocess.run(  # noqa: S603 -- executable is checksum-verified package data.
        (str(executable.path), "--version"),
        capture_output=True,
        check=True,
        text=True,
    )

    assert completed.stdout.startswith(f"ripgrep {executable.version}")
