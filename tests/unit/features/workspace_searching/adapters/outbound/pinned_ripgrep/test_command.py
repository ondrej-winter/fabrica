"""Tests for fixed pinned-ripgrep argument and containment construction."""

from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import command as pinned_ripgrep_command
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.command import PinnedRipgrepCommandBuilder
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import PinnedRipgrepUnavailableError
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import resolve_search_scope
from fabrica.features.workspace_searching.application.dtos import SearchLimits, SearchQuery


def test_linux_pinned_ripgrep_command_for_directory_forwards_literal_glob_and_safe_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pinned_ripgrep_command.platform, "system", lambda: "Linux")
    monkeypatch.setattr(pinned_ripgrep_command.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        pinned_ripgrep_command.SearchSandbox,
        "command_for",
        lambda _self, backend_argv, planned_scope: (*backend_argv, str(planned_scope.canonical_path)),
    )
    (tmp_path / "src").mkdir()
    scope = resolve_search_scope(tmp_path, "src")

    command = PinnedRipgrepCommandBuilder(tmp_path).command_for(
        SearchQuery(pattern="UserService", path="src", glob="**/*.py"), scope, SearchLimits(max_search_file_bytes=1234)
    )

    backend = _backend_arguments(command)
    assert "--json" in backend
    assert "--no-config" in backend
    assert "--hidden" in backend
    assert "--no-follow" in backend
    assert "--no-ignore-parent" in backend
    assert "--ignore-case" in backend
    assert "--max-filesize=1234" in backend
    assert "--glob=!.git/**" in backend
    assert "--glob=!node_modules/**" in backend
    assert "--glob=**/*.py" in backend
    assert "--no-ignore" not in backend
    assert "UserService" in backend
    assert "--max-count=1" not in backend


def test_linux_pinned_ripgrep_command_for_explicit_file_overrides_only_ordinary_ignore_rules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pinned_ripgrep_command.platform, "system", lambda: "Linux")
    monkeypatch.setattr(pinned_ripgrep_command.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        pinned_ripgrep_command.SearchSandbox,
        "command_for",
        lambda _self, backend_argv, planned_scope: (*backend_argv, str(planned_scope.canonical_path)),
    )
    ignored_file = tmp_path / "ignored.py"
    ignored_file.write_text("value = 1\n", encoding="utf-8")
    scope = resolve_search_scope(tmp_path, "ignored.py")

    command = PinnedRipgrepCommandBuilder(tmp_path).command_for(
        SearchQuery(pattern="value", path="ignored.py", case_sensitive=True), scope, SearchLimits()
    )

    backend = _backend_arguments(command)
    assert "--no-ignore" in backend
    assert "--case-sensitive" in backend
    assert "--glob=!.git/**" in backend
    assert "--glob=!node_modules/**" in backend


def test_pinned_ripgrep_command_rejects_an_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_file = tmp_path / "source.py"
    source_file.write_text("needle\n", encoding="utf-8")
    scope = resolve_search_scope(tmp_path, "source.py")
    monkeypatch.setattr(pinned_ripgrep_command.platform, "system", lambda: "Windows")
    monkeypatch.setattr(pinned_ripgrep_command.platform, "machine", lambda: "AMD64")

    with pytest.raises(PinnedRipgrepUnavailableError, match="unavailable"):
        PinnedRipgrepCommandBuilder(tmp_path).command_for(SearchQuery(pattern="needle"), scope, SearchLimits())


def _backend_arguments(command: tuple[str, ...]) -> tuple[str, ...]:
    executable_index = next(index for index, argument in enumerate(command) if argument.endswith("/rg"))
    return command[executable_index:-1]
