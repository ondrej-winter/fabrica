"""Select and verify the sole supported packaged ripgrep executable."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

_RIPGREP_VERSION = "15.2.0"
_BINARY_PACKAGE = "fabrica.features.workspace_searching.adapters.outbound.ripgrep_binaries"
_MANIFEST_NAME = "sha256.json"


@dataclass(slots=True)
class PinnedRipgrepUnavailableError(Exception):
    """Raised when the required verified package-data backend is unavailable."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class PinnedRipgrepExecutable:
    """A verified executable selected from the immutable supported platform set."""

    path: Path
    version: str
    platform_key: str


def verified_pinned_ripgrep_executable() -> PinnedRipgrepExecutable:
    """Return the supported host's packaged ripgrep executable after integrity checks."""
    platform_key = _platform_key()
    manifest = _load_manifest()
    if manifest.get("version") != _RIPGREP_VERSION:
        msg = "packaged ripgrep manifest version is unsupported"
        raise PinnedRipgrepUnavailableError(msg)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        msg = "packaged ripgrep manifest is malformed"
        raise PinnedRipgrepUnavailableError(msg)
    artifact = artifacts.get(platform_key)
    if not isinstance(artifact, dict):
        msg = "packaged ripgrep backend is unavailable for this platform"
        raise PinnedRipgrepUnavailableError(msg)
    relative_path = artifact.get("path")
    expected_sha256 = artifact.get("sha256")
    if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
        msg = "packaged ripgrep artifact metadata is malformed"
        raise PinnedRipgrepUnavailableError(msg)
    executable = Path(str(files(_BINARY_PACKAGE).joinpath(relative_path)))
    _verify_executable(executable, expected_sha256)
    return PinnedRipgrepExecutable(path=executable, version=_RIPGREP_VERSION, platform_key=platform_key)


def _platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-x86_64"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "darwin-arm64"
    msg = "packaged ripgrep backend is unavailable for this platform"
    raise PinnedRipgrepUnavailableError(msg)


def _load_manifest() -> dict[str, object]:
    try:
        payload = files(_BINARY_PACKAGE).joinpath(_MANIFEST_NAME).read_text(encoding="utf-8")
        manifest = json.loads(payload)
    except (OSError, json.JSONDecodeError) as err:
        msg = "packaged ripgrep manifest could not be read"
        raise PinnedRipgrepUnavailableError(msg) from err
    if not isinstance(manifest, dict):
        msg = "packaged ripgrep manifest is malformed"
        raise PinnedRipgrepUnavailableError(msg)
    return manifest


def _verify_executable(executable: Path, expected_sha256: str) -> None:
    try:
        mode = executable.stat().st_mode
        if not stat.S_ISREG(mode) or not os.access(executable, os.X_OK):
            msg = "packaged ripgrep executable is unavailable"
            raise PinnedRipgrepUnavailableError(msg)
        with executable.open("rb") as executable_file:
            actual_sha256 = hashlib.file_digest(executable_file, "sha256").hexdigest()
    except OSError as err:
        msg = "packaged ripgrep executable is unavailable"
        raise PinnedRipgrepUnavailableError(msg) from err
    if actual_sha256 != expected_sha256:
        msg = "packaged ripgrep executable checksum does not match"
        raise PinnedRipgrepUnavailableError(msg)


__all__ = ["PinnedRipgrepExecutable", "PinnedRipgrepUnavailableError", "verified_pinned_ripgrep_executable"]
