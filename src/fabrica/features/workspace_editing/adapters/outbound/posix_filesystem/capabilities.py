"""Actual-workspace production capability evidence for POSIX patch mutation."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class PosixPatchCapabilityStatus(StrEnum):
    """Observed status for one required production capability."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PosixPatchCapabilityProbe:
    """Result for one required production capability."""

    name: str
    status: PosixPatchCapabilityStatus
    detail: str


@dataclass(frozen=True, slots=True)
class PosixPatchWorkspaceCapabilityEvidence:
    """Immutable production capability evidence collected for one workspace."""

    platform: str
    machine: str
    workspace_device: int | None
    filesystem_type: str
    backend: str
    probes: tuple[PosixPatchCapabilityProbe, ...]

    @property
    def production_ready(self) -> bool:
        """Return whether every required production capability is proven."""
        return bool(self.probes) and all(probe.status is PosixPatchCapabilityStatus.SUPPORTED for probe in self.probes)

    @property
    def unsupported_reasons(self) -> tuple[str, ...]:
        """Return stable capability names that block production mutation."""
        return tuple(probe.name for probe in self.probes if probe.status is not PosixPatchCapabilityStatus.SUPPORTED)


def collect_posix_patch_workspace_capability_evidence(
    workspace_root: Path,
) -> PosixPatchWorkspaceCapabilityEvidence:
    """Collect fail-closed production evidence against the actual workspace."""
    try:
        resolved_root = workspace_root.resolve(strict=True)
        root_stat = resolved_root.stat()
    except OSError as err:
        return PosixPatchWorkspaceCapabilityEvidence(
            platform=sys.platform,
            machine=platform.machine(),
            workspace_device=None,
            filesystem_type="unknown",
            backend=_backend_name(),
            probes=(
                PosixPatchCapabilityProbe(
                    name="workspace_root",
                    status=PosixPatchCapabilityStatus.FAILED,
                    detail=f"{type(err).__name__}: errno={err.errno}",
                ),
            ),
        )

    return PosixPatchWorkspaceCapabilityEvidence(
        platform=sys.platform,
        machine=platform.machine(),
        workspace_device=root_stat.st_dev,
        filesystem_type=_filesystem_type(resolved_root),
        backend=_backend_name(),
        probes=(
            _platform_scope_probe(),
            _capture("descriptor_rooted_traversal", lambda: _directory_fd_probe(resolved_root)),
            _no_follow_probe(),
            _native_no_replace_probe(),
            _supervised_helper_ownership_probe(),
        ),
    )


def _capture(name: str, probe: Callable[[], PosixPatchCapabilityProbe]) -> PosixPatchCapabilityProbe:
    try:
        return probe()
    except OSError as err:
        return PosixPatchCapabilityProbe(
            name=name,
            status=PosixPatchCapabilityStatus.FAILED,
            detail=f"{type(err).__name__}: errno={err.errno}",
        )


def _platform_scope_probe() -> PosixPatchCapabilityProbe:
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return PosixPatchCapabilityProbe(
            name="platform_scope",
            status=PosixPatchCapabilityStatus.SUPPORTED,
            detail="macOS Apple Silicon is the v1 release target",
        )
    if sys.platform == "linux":
        return PosixPatchCapabilityProbe(
            name="platform_scope",
            status=PosixPatchCapabilityStatus.SUPPORTED,
            detail="Linux remains a candidate pending per-filesystem backend proof",
        )
    return PosixPatchCapabilityProbe(
        name="platform_scope",
        status=PosixPatchCapabilityStatus.UNSUPPORTED,
        detail="v1 production mutation targets macOS Apple Silicon and Linux only",
    )


def _directory_fd_probe(workspace_root: Path) -> PosixPatchCapabilityProbe:
    required = ("O_DIRECTORY", "O_NOFOLLOW")
    if not all(hasattr(os, name) for name in required):
        return PosixPatchCapabilityProbe(
            name="descriptor_rooted_traversal",
            status=PosixPatchCapabilityStatus.UNSUPPORTED,
            detail="Python does not expose required directory descriptor flags",
        )
    descriptor = os.open(workspace_root, os.O_RDONLY | os.O_DIRECTORY)
    os.close(descriptor)
    return PosixPatchCapabilityProbe(
        name="descriptor_rooted_traversal",
        status=PosixPatchCapabilityStatus.SUPPORTED,
        detail="workspace root opened through a directory descriptor",
    )


def _no_follow_probe() -> PosixPatchCapabilityProbe:
    if hasattr(os, "O_NOFOLLOW"):
        return PosixPatchCapabilityProbe(
            name="no_follow_path_resolution",
            status=PosixPatchCapabilityStatus.SUPPORTED,
            detail="Python exposes O_NOFOLLOW",
        )
    return PosixPatchCapabilityProbe(
        name="no_follow_path_resolution",
        status=PosixPatchCapabilityStatus.UNSUPPORTED,
        detail="Python does not expose O_NOFOLLOW",
    )


def _native_no_replace_probe() -> PosixPatchCapabilityProbe:
    if sys.platform == "darwin":
        detail = "AP-02 has not yet proven renameatx_np with RENAME_EXCL and RENAME_NOFOLLOW_ANY"
        name = "macos_renameatx_np_no_replace"
    elif sys.platform == "linux":
        detail = "AP-02 has not yet proven renameat2 with RENAME_NOREPLACE"
        name = "linux_renameat2_no_replace"
    else:
        detail = "no selected native no-replace backend exists for this platform"
        name = "native_no_replace"
    return PosixPatchCapabilityProbe(name, PosixPatchCapabilityStatus.UNSUPPORTED, detail)


def _supervised_helper_ownership_probe() -> PosixPatchCapabilityProbe:
    return PosixPatchCapabilityProbe(
        name="supervised_helper_ownership",
        status=PosixPatchCapabilityStatus.UNSUPPORTED,
        detail="AP-03 has not yet proven journal-backed helper terminal-state and termination guarantees",
    )


def _backend_name() -> str:
    if sys.platform == "darwin":
        return "darwin_renameatx_np_supervised_helper_v1"
    if sys.platform == "linux":
        return "linux_renameat2_supervised_helper_v1"
    return "unselected"


def _filesystem_type(path: Path) -> str:
    if sys.platform == "darwin":
        command = ("stat", "-f", "%T", str(path))
    elif sys.platform == "linux":
        command = ("stat", "-f", "-c", "%T", str(path))
    else:
        return "unsupported-platform"
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5)  # noqa: S603
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


__all__ = [
    "PosixPatchCapabilityProbe",
    "PosixPatchCapabilityStatus",
    "PosixPatchWorkspaceCapabilityEvidence",
    "collect_posix_patch_workspace_capability_evidence",
]
