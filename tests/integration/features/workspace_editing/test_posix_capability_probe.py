"""Integration tests for the non-production apply_patch POSIX capability probe."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

_PROBE_PATH = Path("scripts/apply_patch_posix_capability_probe.py")


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="Task 5 probe targets macOS/Linux POSIX")
def test_posix_capability_probe_reports_fail_closed_decision(tmp_path: Path) -> None:
    probe = _load_probe_module()

    report = probe.run_probe(tmp_path)

    assert report["schema_version"] == 1
    assert report["supported_platform"] is True
    assert report["workspace"]["filesystem_type"]
    assert isinstance(report["workspace"]["device"], int)
    assert report["selected_backend"] in {
        "darwin_renameatx_np_supervised_helper_v1",
        "linux_renameat2_supervised_helper_v1",
    }
    assert report["capabilities"]["workspace_root_dir_fd_traversal"]["status"] == "supported"
    assert report["capabilities"]["no_follow_open"]["status"] == "supported"
    assert report["capabilities"]["exclusive_create_no_replace"]["status"] == "supported"
    assert report["capabilities"]["pinned_identities"]["status"] == "supported"
    assert report["capabilities"]["link_count_inspection"]["status"] == "supported"
    assert report["capabilities"]["mode_bit_inspection_and_application"]["status"] == "supported"
    assert report["capabilities"]["file_fsync"]["status"] == "supported"
    assert report["capabilities"]["directory_fsync"]["status"] == "supported"
    assert report["capabilities"]["regular_and_special_file_classification"]["status"] == "supported"
    assert report["capabilities"]["stdlib_no_replace_rename"] == {
        "status": "unsupported",
        "detail": (
            "Python 3.13 stdlib exposes os.rename/os.replace with dir_fd support but no portable "
            "RENAME_NOREPLACE or renameat2 wrapper; adapter needs ctypes/platform syscall support or "
            "a different pre-commit design"
        ),
        "standard_library_sufficient": False,
    }
    assert report["capabilities"]["bounded_in_process_cleanup"] == {
        "status": "unsupported",
        "detail": (
            "A hard in-process cleanup deadline cannot be proven for potentially blocking POSIX syscalls; "
            "Task 5 selects supervised helper-process/recovery ownership for production design"
        ),
        "standard_library_sufficient": False,
    }
    assert report["fail_closed"] is True
    assert report["decision"] == "requires_platform_specific_no_replace_rename_before_production"


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="Task 5 probe targets macOS/Linux POSIX")
def test_posix_capability_probe_cli_emits_json_evidence(tmp_path: Path) -> None:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(_PROBE_PATH), "--workspace", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    report = json.loads(completed.stdout)

    assert report["platform"]["python_version"]
    assert report["workspace"]["path"] == str(tmp_path.resolve())
    assert report["workspace"]["device"] == tmp_path.stat().st_dev
    assert "stdlib_no_replace_rename" in report["unsupported_reasons"]
    assert "bounded_in_process_cleanup" in report["unsupported_reasons"]


def _load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apply_patch_posix_capability_probe", _PROBE_PATH)
    if spec is None or spec.loader is None:
        msg = "could not load apply_patch POSIX capability probe"
        raise AssertionError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
