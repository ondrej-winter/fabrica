"""Probe POSIX filesystem primitives required by the apply_patch adapter.

This non-production feasibility probe remains outside the ``src/fabrica`` package
so platform capability evidence can be collected independently of production
workspace-editing composition.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

type ProbeStatus = Literal["supported", "unsupported", "failed"]
MIN_EXPECTED_HARD_LINK_COUNT = 2
STRICT_FILE_MODE = 0o600


@dataclass(frozen=True, slots=True)
class CapabilityProbe:
    """One filesystem capability probe result."""

    status: ProbeStatus
    detail: str
    standard_library_sufficient: bool

    def to_json(self) -> dict[str, object]:
        """Return a stable JSON-compatible representation."""
        return {
            "status": self.status,
            "detail": self.detail,
            "standard_library_sufficient": self.standard_library_sufficient,
        }


def run_probe(workspace: Path) -> dict[str, object]:
    """Run capability probes against a temporary directory under ``workspace``."""
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    probe_root = Path(tempfile.mkdtemp(prefix="fabrica-apply-patch-posix-probe-", dir=workspace))
    try:
        capabilities = {
            "workspace_root_dir_fd_traversal": _capture(lambda: _probe_dir_fd_traversal(probe_root)),
            "no_follow_open": _capture(lambda: _probe_no_follow_open(probe_root)),
            "exclusive_create_no_replace": _capture(lambda: _probe_exclusive_create_no_replace(probe_root)),
            "stdlib_no_replace_rename": _capture(_probe_stdlib_no_replace_rename),
            "pinned_identities": _capture(lambda: _probe_pinned_identities(probe_root)),
            "link_count_inspection": _capture(lambda: _probe_link_count_inspection(probe_root)),
            "mode_bit_inspection_and_application": _capture(lambda: _probe_mode_bits(probe_root)),
            "file_fsync": _capture(lambda: _probe_file_fsync(probe_root)),
            "directory_fsync": _capture(lambda: _probe_directory_fsync(probe_root)),
            "regular_and_special_file_classification": _capture(lambda: _probe_file_classification(probe_root)),
            "bounded_in_process_cleanup": _capture(_probe_bounded_cleanup_model),
        }
        supported_platform = sys.platform in {"darwin", "linux"}
        unsupported = [name for name, probe in capabilities.items() if probe.status != "supported"]
        return {
            "schema_version": 1,
            "supported_platform": supported_platform,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
                "sys_platform": sys.platform,
            },
            "workspace": {
                "path": str(workspace),
                "filesystem_type": _filesystem_type(workspace),
                "device": workspace.stat().st_dev,
            },
            "selected_backend": _selected_backend(),
            "capabilities": {name: probe.to_json() for name, probe in capabilities.items()},
            "fail_closed": bool(unsupported or not supported_platform),
            "unsupported_reasons": unsupported if supported_platform else ["unsupported_platform", *unsupported],
            "decision": _decision(capabilities, supported_platform=supported_platform),
        }
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)


def _capture(probe: Callable[[], CapabilityProbe]) -> CapabilityProbe:
    try:
        return probe()
    except OSError as err:
        return CapabilityProbe(
            status="failed",
            detail=f"{err.__class__.__name__}: errno={err.errno}",
            standard_library_sufficient=False,
        )


def _probe_dir_fd_traversal(root: Path) -> CapabilityProbe:
    child = root / "child"
    child.mkdir()
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        child_fd = os.open("child", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        os.close(child_fd)
    finally:
        os.close(root_fd)
    return CapabilityProbe(
        "supported",
        "opened child directory handle relative to pinned root fd",
        standard_library_sufficient=True,
    )


def _probe_no_follow_open(root: Path) -> CapabilityProbe:
    target = root / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = root / "link.txt"
    link.symlink_to(target.name)
    try:
        fd = os.open(link, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as err:
        if err.errno == errno.ELOOP:
            return CapabilityProbe(
                "supported",
                "O_NOFOLLOW rejected symlink traversal with ELOOP",
                standard_library_sufficient=True,
            )
        raise
    else:
        os.close(fd)
        return CapabilityProbe(
            "failed",
            "O_NOFOLLOW unexpectedly opened a symlink",
            standard_library_sufficient=False,
        )


def _probe_exclusive_create_no_replace(root: Path) -> CapabilityProbe:
    path = root / "exclusive.txt"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        second_fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return CapabilityProbe(
            "supported",
            "O_CREAT|O_EXCL rejects existing destination",
            standard_library_sufficient=True,
        )
    else:
        os.close(second_fd)
        return CapabilityProbe(
            "failed",
            "exclusive create unexpectedly replaced an existing path",
            standard_library_sufficient=False,
        )


def _probe_stdlib_no_replace_rename() -> CapabilityProbe:
    return CapabilityProbe(
        status="unsupported",
        detail=(
            "Python 3.14 stdlib exposes os.rename/os.replace with dir_fd support but no portable "
            "RENAME_NOREPLACE or renameat2 wrapper; adapter needs ctypes/platform syscall support or "
            "a different pre-commit design"
        ),
        standard_library_sufficient=False,
    )


def _probe_pinned_identities(root: Path) -> CapabilityProbe:
    path = root / "identity.txt"
    path.write_text("identity", encoding="utf-8")
    stat_result = path.stat(follow_symlinks=False)
    if stat_result.st_dev <= 0 or stat_result.st_ino <= 0:
        return CapabilityProbe(
            "failed",
            "st_dev/st_ino identity fields were not populated",
            standard_library_sufficient=False,
        )
    return CapabilityProbe(
        "supported",
        "stat exposes stable st_dev and st_ino identity evidence",
        standard_library_sufficient=True,
    )


def _probe_link_count_inspection(root: Path) -> CapabilityProbe:
    path = root / "linked.txt"
    linked = root / "linked-again.txt"
    path.write_text("linked", encoding="utf-8")
    os.link(path, linked)
    link_count = path.stat(follow_symlinks=False).st_nlink
    if link_count < MIN_EXPECTED_HARD_LINK_COUNT:
        return CapabilityProbe(
            "failed",
            f"expected hard-link count >= {MIN_EXPECTED_HARD_LINK_COUNT}, got {link_count}",
            standard_library_sufficient=False,
        )
    return CapabilityProbe(
        "supported",
        f"st_nlink reports hard-link count {link_count}",
        standard_library_sufficient=True,
    )


def _probe_mode_bits(root: Path) -> CapabilityProbe:
    path = root / "mode.txt"
    path.write_text("mode", encoding="utf-8")
    path.chmod(STRICT_FILE_MODE)
    mode = path.stat(follow_symlinks=False).st_mode & 0o777
    if mode != STRICT_FILE_MODE:
        return CapabilityProbe(
            "failed",
            f"expected mode 0600, got {mode:o}",
            standard_library_sufficient=False,
        )
    return CapabilityProbe(
        "supported",
        "chmod/stat preserve portable permission bits",
        standard_library_sufficient=True,
    )


def _probe_file_fsync(root: Path) -> CapabilityProbe:
    path = root / "fsync.txt"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, STRICT_FILE_MODE)
    try:
        os.write(fd, b"durable")
        os.fsync(fd)
    finally:
        os.close(fd)
    return CapabilityProbe("supported", "os.fsync succeeds on regular file handle", standard_library_sufficient=True)


def _probe_directory_fsync(root: Path) -> CapabilityProbe:
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return CapabilityProbe("supported", "os.fsync succeeds on directory handle", standard_library_sufficient=True)


def _probe_file_classification(root: Path) -> CapabilityProbe:
    regular = root / "regular.txt"
    directory = root / "directory"
    regular.write_text("regular", encoding="utf-8")
    directory.mkdir()
    if not regular.is_file() or not directory.is_dir():
        return CapabilityProbe(
            "failed",
            "pathlib/os stat could not classify regular file and directory",
            standard_library_sufficient=False,
        )
    return CapabilityProbe(
        "supported",
        "stat classification distinguishes regular files and directories",
        standard_library_sufficient=True,
    )


def _probe_bounded_cleanup_model() -> CapabilityProbe:
    return CapabilityProbe(
        status="unsupported",
        detail=(
            "A hard in-process cleanup deadline cannot be proven for potentially blocking POSIX syscalls; "
            "Task 5 selects supervised helper-process/recovery ownership for production design"
        ),
        standard_library_sufficient=False,
    )


def _filesystem_type(path: Path) -> str:
    if sys.platform == "darwin":
        command = ("stat", "-f", "%T", str(path))
    elif sys.platform == "linux":
        command = ("stat", "-f", "-c", "%T", str(path))
    else:
        return "unsupported-platform"

    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5)  # noqa: S603
    except OSError, subprocess.SubprocessError:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _decision(capabilities: Mapping[str, CapabilityProbe], *, supported_platform: bool) -> str:
    if not supported_platform:
        return "fail_closed_unsupported_platform"
    if capabilities["stdlib_no_replace_rename"].status != "supported":
        return "requires_platform_specific_no_replace_rename_before_production"
    if capabilities["bounded_in_process_cleanup"].status != "supported":
        return "requires_supervised_helper_process_recovery_model"
    if any(probe.status != "supported" for probe in capabilities.values()):
        return "fail_closed_unsupported_filesystem"
    return "standard_library_primitives_sufficient"


def _selected_backend() -> str:
    if sys.platform == "darwin":
        return "darwin_renameatx_np_supervised_helper_v1"
    if sys.platform == "linux":
        return "linux_renameat2_supervised_helper_v1"
    return "unselected"


def main() -> int:
    """Run the probe from the command line and emit compact JSON evidence."""
    parser = argparse.ArgumentParser(description="Probe POSIX capabilities required by the apply_patch design.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace directory under which a temporary probe directory is created.",
    )
    args = parser.parse_args()
    sys.stdout.write(json.dumps(run_probe(args.workspace), sort_keys=True, separators=(",", ":")))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
