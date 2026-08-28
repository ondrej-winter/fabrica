"""Integration regressions for workspace-search subprocess containment."""

import subprocess
import sys
from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import SearchSandbox, resolve_search_scope

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox-exec containment coverage")


def test_macos_search_sandbox_blocks_a_post_resolution_symlink_escape(tmp_path: Path) -> None:
    selected_file = tmp_path / "selected.txt"
    selected_file.write_text("inside\n", encoding="utf-8")
    outside_file = tmp_path.parent / "outside-search-scope.txt"
    outside_file.write_text("outside-secret\n", encoding="utf-8")
    scope = resolve_search_scope(tmp_path, "selected.txt")
    selected_file.unlink()
    selected_file.symlink_to(outside_file)

    completed = subprocess.run(  # noqa: S603 -- the test executes a fixed sandboxed /bin/cat command.
        SearchSandbox(tmp_path).command_for(("/bin/cat",), scope),
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode != 0
    assert "outside-secret" not in completed.stdout
