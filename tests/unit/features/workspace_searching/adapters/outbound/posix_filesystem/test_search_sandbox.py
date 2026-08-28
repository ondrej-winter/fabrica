"""Tests for fail-closed workspace-search subprocess containment planning."""

from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import (
    SearchSandbox,
    SearchSandboxUnavailableError,
    resolve_search_scope,
)


def test_search_sandbox_rejects_empty_backend_command(tmp_path: Path) -> None:
    scope = _scope(tmp_path)

    with pytest.raises(ValueError, match="must not be empty"):
        SearchSandbox(tmp_path).command_for((), scope)


def test_search_sandbox_rejects_scope_outside_its_workspace(tmp_path: Path) -> None:
    other_workspace = tmp_path.parent / "other-workspace"
    other_workspace.mkdir()
    scope = _scope(other_workspace)

    with pytest.raises(SearchSandboxUnavailableError, match="must remain inside"):
        SearchSandbox(tmp_path).command_for(("/usr/bin/true",), scope)


def test_search_sandbox_fails_closed_when_platform_capability_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope = _scope(tmp_path)
    monkeypatch.setattr(
        "fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.search_sandbox.sys.platform", "win32"
    )

    with pytest.raises(SearchSandboxUnavailableError, match="unsupported"):
        SearchSandbox(tmp_path).command_for(("/usr/bin/true",), scope)


def _scope(workspace_root: Path):
    source_file = workspace_root / "source.py"
    source_file.write_text("value = 1\n", encoding="utf-8")
    return resolve_search_scope(workspace_root, "source.py")
