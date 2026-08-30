"""Integration checks for the selected local pinned ripgrep package artifact."""

import platform
import subprocess

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import (
    verified_pinned_ripgrep_executable,
)

pytestmark = pytest.mark.skipif(
    (platform.system(), platform.machine()) not in {("Linux", "x86_64"), ("Darwin", "arm64"), ("Darwin", "aarch64")},
    reason="supported package-data ripgrep conformance",
)


def test_pinned_ripgrep_executable_reports_the_pinned_release_version() -> None:
    executable = verified_pinned_ripgrep_executable()

    completed = subprocess.run(  # noqa: S603 -- executable is checksum-verified package data.
        (str(executable.path), "--version"),
        capture_output=True,
        check=True,
        text=True,
    )

    assert completed.stdout.startswith(f"ripgrep {executable.version}")
