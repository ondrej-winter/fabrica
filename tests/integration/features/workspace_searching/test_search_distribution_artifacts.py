"""Conformance checks for clean installs of workspace-searching distributions."""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest

_DISTRIBUTION_ARTIFACTS_ENVIRONMENT_VARIABLE = "FABRICA_DISTRIBUTION_ARTIFACTS"
_EXPECTED_DISTRIBUTION_COUNT = 2
_REPRESENTATIVE_SEARCH_SOURCE = "needle\n"
_REPRESENTATIVE_SEARCH_PATTERN = "needle"

pytestmark = pytest.mark.skipif(
    (platform.system(), platform.machine()) not in {("Linux", "x86_64"), ("Darwin", "arm64"), ("Darwin", "aarch64")},
    reason="supported package-data distribution conformance",
)


def test_built_distributions_include_and_execute_the_verified_pinned_ripgrep_binary(tmp_path: Path) -> None:
    """Install each requested artifact outside the checkout and search a fixture."""
    artifact_paths = _distribution_artifact_paths()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_file = workspace / "source.txt"
    source_file.write_text(_REPRESENTATIVE_SEARCH_SOURCE, encoding="utf-8")

    for artifact_path in artifact_paths:
        virtual_environment = tmp_path / artifact_path.stem
        _run(("uv", "venv", str(virtual_environment), "--python", sys.executable), cwd=tmp_path)
        interpreter = _virtual_environment_interpreter(virtual_environment)
        _run(("uv", "pip", "install", "--python", str(interpreter), "--no-deps", str(artifact_path)), cwd=tmp_path)

        completed = _run(
            (
                str(interpreter),
                "-c",
                _installed_artifact_probe(),
                str(source_file),
                _REPRESENTATIVE_SEARCH_PATTERN,
            ),
            cwd=tmp_path,
        )

        evidence = json.loads(completed.stdout)
        assert evidence["path"].endswith("/rg")
        assert evidence["version"] == "15.2.0"
        assert evidence["search_event_type"] == "match"
        assert evidence["checksum_matches_manifest"] is True
        assert evidence["is_executable"] is True


def _distribution_artifact_paths() -> tuple[Path, ...]:
    raw_artifacts = os.environ.get(_DISTRIBUTION_ARTIFACTS_ENVIRONMENT_VARIABLE)
    if raw_artifacts is None:
        pytest.skip(f"{_DISTRIBUTION_ARTIFACTS_ENVIRONMENT_VARIABLE} is required for distribution conformance")
    artifact_paths = tuple(
        Path(expanded_artifact).resolve()
        for raw_artifact in raw_artifacts.split(os.pathsep)
        for expanded_artifact in Path.cwd().glob(raw_artifact)
    )
    if len(artifact_paths) != _EXPECTED_DISTRIBUTION_COUNT or any(not path.is_file() for path in artifact_paths):
        msg = f"{_DISTRIBUTION_ARTIFACTS_ENVIRONMENT_VARIABLE} must name one wheel and one source distribution"
        raise ValueError(msg)
    return artifact_paths


def _virtual_environment_interpreter(virtual_environment: Path) -> Path:
    scripts_directory = "Scripts" if sys.platform == "win32" else "bin"
    executable_name = "python.exe" if sys.platform == "win32" else "python"
    return virtual_environment / scripts_directory / executable_name


def _installed_artifact_probe() -> str:
    return """
import hashlib
import json
import os
import stat
import subprocess
import sys

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import (
    verified_pinned_ripgrep_executable,
)
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import manifest as manifest_module

executable = verified_pinned_ripgrep_executable()
manifest = manifest_module._load_manifest()
artifact = manifest["artifacts"][executable.platform_key]
with executable.path.open("rb") as executable_file:
    actual_sha256 = hashlib.file_digest(executable_file, "sha256").hexdigest()
completed = subprocess.run(
    (str(executable.path), "--json", "--no-config", "--case-sensitive", sys.argv[2], sys.argv[1]),
    capture_output=True,
    check=True,
    text=True,
)
event = next(json.loads(line) for line in completed.stdout.splitlines() if json.loads(line)["type"] == "match")
print(json.dumps({
    "path": str(executable.path),
    "version": executable.version,
    "search_event_type": event["type"],
    "checksum_matches_manifest": actual_sha256 == artifact["sha256"],
    "is_executable": stat.S_ISREG(executable.path.stat().st_mode) and os.access(executable.path, os.X_OK),
}))
"""


def _run(command: tuple[str, ...], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, check=True, cwd=cwd, text=True)  # noqa: S603
