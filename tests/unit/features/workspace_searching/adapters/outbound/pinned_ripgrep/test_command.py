"""Tests for fixed pinned-ripgrep argument and containment construction."""

from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import command as pinned_ripgrep_command
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.command import PinnedRipgrepCommandBuilder
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import (
    PinnedRipgrepExecutable,
    PinnedRipgrepUnavailableError,
)
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import resolve_search_scope
from fabrica.features.workspace_searching.application.dtos import SearchLimits, SearchQuery


def test_linux_pinned_ripgrep_command_directly_invokes_the_verified_executable_with_the_canonical_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        pinned_ripgrep_command,
        "verified_pinned_ripgrep_executable",
        lambda: PinnedRipgrepExecutable(Path("/package/linux_x86_64/rg"), "15.2.0", "linux-x86_64"),
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
    assert command[0] == "/package/linux_x86_64/rg"
    assert command[-1] == str(scope.canonical_path)
    assert "bwrap" not in command


def test_linux_pinned_ripgrep_command_for_explicit_file_overrides_only_ordinary_ignore_rules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        pinned_ripgrep_command,
        "verified_pinned_ripgrep_executable",
        lambda: PinnedRipgrepExecutable(Path("/package/linux_x86_64/rg"), "15.2.0", "linux-x86_64"),
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

    def unavailable() -> PinnedRipgrepExecutable:
        message = "unavailable"
        raise PinnedRipgrepUnavailableError(message)

    monkeypatch.setattr(pinned_ripgrep_command, "verified_pinned_ripgrep_executable", unavailable)

    with pytest.raises(PinnedRipgrepUnavailableError, match="unavailable"):
        PinnedRipgrepCommandBuilder(tmp_path).command_for(SearchQuery(pattern="needle"), scope, SearchLimits())


def test_macos_pinned_ripgrep_command_directly_invokes_the_verified_executable_with_the_canonical_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_file = tmp_path / "src" / "source.py"
    source_file.parent.mkdir()
    source_file.write_text("needle\n", encoding="utf-8")
    scope = resolve_search_scope(tmp_path, "src")
    executable = PinnedRipgrepExecutable(Path("/package/macos_arm64/rg"), "15.2.0", "darwin-arm64")
    monkeypatch.setattr(pinned_ripgrep_command, "verified_pinned_ripgrep_executable", lambda: executable)

    command = PinnedRipgrepCommandBuilder(tmp_path).command_for(SearchQuery(pattern="needle"), scope, SearchLimits())

    assert command[0] == str(executable.path)
    assert command[-1] == str(scope.canonical_path)
    assert "container" not in command
    assert "--no-config" in command
    assert "--no-follow" in command


def _backend_arguments(command: tuple[str, ...]) -> tuple[str, ...]:
    executable_index = next(index for index, argument in enumerate(command) if argument.endswith("/rg"))
    return command[executable_index:-1]
