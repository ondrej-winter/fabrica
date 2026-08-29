"""Fail-closed Apple Container execution for workspace search on macOS."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.path_resolution import SearchScope

_CONTAINER_EXECUTABLE = "container"
_CONTAINER_WORKSPACE_MOUNT = Path("/workspace")
_IMAGE_METADATA_PACKAGE = "fabrica.features.workspace_searching.adapters.outbound.search_images"
_IMAGE_METADATA_NAME = "macos_arm64.json"
_MINIMUM_MACOS_MAJOR_VERSION = 26


@dataclass(slots=True)
class AppleContainerUnavailableError(Exception):
    """Raised when the required verified Apple Container image is unavailable."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class AppleContainerSearchImage:
    """A locally provisioned OCI image selected by immutable digest."""

    reference: str
    digest: str


@dataclass(frozen=True, slots=True)
class AppleContainerSearchCommandBuilder:
    """Build the sole supported read-only Apple Container search command."""

    workspace_root: Path

    def command_for(self, backend_argv: tuple[str, ...], scope: SearchScope) -> tuple[str, ...]:
        """Return a fixed, no-network, read-only container command for one scope."""
        if not backend_argv:
            msg = "backend command must not be empty"
            raise ValueError(msg)
        _require_supported_macos()
        root = self.workspace_root.resolve(strict=True)
        if not scope.canonical_path.is_relative_to(root):
            msg = "search scope must remain inside the configured workspace"
            raise AppleContainerUnavailableError(msg)
        image = verified_apple_container_search_image()
        scope_path = _CONTAINER_WORKSPACE_MOUNT / scope.workspace_relative_path
        mount = f"type=bind,source={root},target={_CONTAINER_WORKSPACE_MOUNT},readonly"
        return (
            _container_executable(),
            "run",
            "--rm",
            "--read-only",
            "--no-dns",
            "--mount",
            mount,
            "--workdir",
            str(_CONTAINER_WORKSPACE_MOUNT),
            image.reference,
            *backend_argv,
            str(scope_path),
        )


def verified_apple_container_search_image() -> AppleContainerSearchImage:
    """Verify the locally provisioned image identity without pulling from a registry."""
    metadata = _load_image_metadata()
    reference = metadata.get("reference")
    digest = metadata.get("digest")
    if not isinstance(reference, str) or not isinstance(digest, str) or not digest.startswith("sha256:"):
        msg = "Apple Container search image metadata is malformed"
        raise AppleContainerUnavailableError(msg)
    actual_digest = _inspect_local_image_digest(_container_executable(), reference)
    if actual_digest != digest:
        msg = "Apple Container search image digest does not match"
        raise AppleContainerUnavailableError(msg)
    return AppleContainerSearchImage(reference=reference, digest=digest)


def _require_supported_macos() -> None:
    if platform.system().lower() != "darwin" or platform.machine().lower() not in {"arm64", "aarch64"}:
        msg = "Apple Container workspace search is supported only on macOS Apple Silicon"
        raise AppleContainerUnavailableError(msg)
    version = platform.mac_ver()[0]
    major_version = version.split(".", maxsplit=1)[0]
    if not major_version.isdigit() or int(major_version) < _MINIMUM_MACOS_MAJOR_VERSION:
        msg = "Apple Container workspace search requires macOS 26 or later"
        raise AppleContainerUnavailableError(msg)


def _container_executable() -> str:
    executable = shutil.which(_CONTAINER_EXECUTABLE)
    if executable is None:
        msg = "macOS workspace search containment requires Apple Container"
        raise AppleContainerUnavailableError(msg)
    return executable


def _load_image_metadata() -> dict[str, object]:
    try:
        payload = files(_IMAGE_METADATA_PACKAGE).joinpath(_IMAGE_METADATA_NAME).read_text(encoding="utf-8")
        metadata = json.loads(payload)
    except (ModuleNotFoundError, OSError, json.JSONDecodeError) as err:
        msg = "Apple Container search image metadata could not be read"
        raise AppleContainerUnavailableError(msg) from err
    if not isinstance(metadata, dict):
        msg = "Apple Container search image metadata is malformed"
        raise AppleContainerUnavailableError(msg)
    return metadata


def _inspect_local_image_digest(container_executable: str, reference: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 -- executable and arguments are fixed adapter-owned values.
            (container_executable, "image", "inspect", "--format", "{{.Digest}}", reference),
            capture_output=True,
            check=True,
            text=True,
        )
    except OSError as err:
        msg = "Apple Container search image is unavailable"
        raise AppleContainerUnavailableError(msg) from err
    except subprocess.CalledProcessError as err:
        msg = "Apple Container search image is unavailable"
        raise AppleContainerUnavailableError(msg) from err
    digest = completed.stdout.strip()
    if not digest.startswith("sha256:"):
        msg = "Apple Container did not report a valid image digest"
        raise AppleContainerUnavailableError(msg)
    return digest


__all__ = [
    "AppleContainerSearchCommandBuilder",
    "AppleContainerSearchImage",
    "AppleContainerUnavailableError",
    "verified_apple_container_search_image",
]
