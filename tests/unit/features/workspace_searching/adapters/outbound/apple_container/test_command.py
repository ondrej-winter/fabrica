"""Tests for fixed, digest-verified Apple Container search commands."""

import subprocess
from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.apple_container import command
from fabrica.features.workspace_searching.adapters.outbound.apple_container.command import (
    AppleContainerSearchCommandBuilder,
    AppleContainerUnavailableError,
    verified_apple_container_search_image,
)
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import resolve_search_scope


def test_command_for_mounts_only_the_workspace_read_only_and_rewrites_the_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_file = tmp_path / "src" / "example.py"
    source_file.parent.mkdir()
    source_file.write_text("needle\n", encoding="utf-8")
    scope = resolve_search_scope(tmp_path, "src")
    _allow_supported_verified_image(monkeypatch)

    assembled = AppleContainerSearchCommandBuilder(tmp_path).command_for(("rg", "--json", "needle"), scope)

    assert assembled[:6] == ("/usr/local/bin/container", "run", "--rm", "--read-only", "--no-dns", "--mount")
    assert assembled[6] == f"type=bind,source={tmp_path.resolve()},target=/workspace,readonly"
    assert assembled[7:10] == ("--workdir", "/workspace", "fabrica/workspace-search:15.2.0")
    assert assembled[10:] == ("rg", "--json", "needle", "/workspace/src")
    assert "pull" not in assembled


def test_command_for_rejects_hosts_outside_the_supported_macos_matrix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_file = tmp_path / "source.py"
    source_file.write_text("needle\n", encoding="utf-8")
    scope = resolve_search_scope(tmp_path, "source.py")
    monkeypatch.setattr(command.platform, "system", lambda: "Linux")

    with pytest.raises(AppleContainerUnavailableError, match="macOS Apple Silicon"):
        AppleContainerSearchCommandBuilder(tmp_path).command_for(("rg",), scope)


def test_command_for_rejects_macos_versions_before_26(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_file = tmp_path / "source.py"
    source_file.write_text("needle\n", encoding="utf-8")
    scope = resolve_search_scope(tmp_path, "source.py")
    monkeypatch.setattr(command.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(command.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(command.platform, "mac_ver", lambda: ("15.7.0", ("", "", ""), ""))

    with pytest.raises(AppleContainerUnavailableError, match="macOS 26"):
        AppleContainerSearchCommandBuilder(tmp_path).command_for(("rg",), scope)


def test_command_for_rejects_a_scope_outside_the_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    other_workspace = tmp_path.parent / "other-workspace"
    other_workspace.mkdir()
    source_file = other_workspace / "source.py"
    source_file.write_text("needle\n", encoding="utf-8")
    scope = resolve_search_scope(other_workspace, "source.py")
    monkeypatch.setattr(command.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(command.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(command.platform, "mac_ver", lambda: ("26.0.0", ("", "", ""), ""))

    with pytest.raises(AppleContainerUnavailableError, match="must remain inside"):
        AppleContainerSearchCommandBuilder(tmp_path).command_for(("rg",), scope)


def test_verified_image_rejects_a_digest_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        command,
        "_load_image_metadata",
        lambda: {"reference": "fabrica/workspace-search:15.2.0", "digest": "sha256:" + "0" * 64},
    )
    monkeypatch.setattr(command, "_container_executable", lambda: "/usr/local/bin/container")
    monkeypatch.setattr(command, "_inspect_local_image_digest", lambda _executable, _reference: "sha256:" + "1" * 64)

    with pytest.raises(AppleContainerUnavailableError, match="does not match"):
        verified_apple_container_search_image()


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"reference": "fabrica/workspace-search:15.2.0"},
        {"reference": "fabrica/workspace-search:15.2.0", "digest": "not-a-digest"},
    ],
)
def test_verified_image_rejects_malformed_metadata(monkeypatch: pytest.MonkeyPatch, metadata: dict[str, str]) -> None:
    monkeypatch.setattr(command, "_load_image_metadata", lambda: metadata)

    with pytest.raises(AppleContainerUnavailableError, match="metadata is malformed"):
        verified_apple_container_search_image()


def test_verified_image_rejects_an_invalid_digest_reported_by_the_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        command,
        "_load_image_metadata",
        lambda: {"reference": "fabrica/workspace-search:15.2.0", "digest": "sha256:" + "0" * 64},
    )
    monkeypatch.setattr(command, "_container_executable", lambda: "/usr/local/bin/container")
    monkeypatch.setattr(command, "_inspect_local_image_digest", lambda _executable, _reference: "not-a-digest")

    with pytest.raises(AppleContainerUnavailableError, match="does not match"):
        verified_apple_container_search_image()


def test_container_executable_fails_closed_when_apple_container_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(command.shutil, "which", lambda _name: None)

    with pytest.raises(AppleContainerUnavailableError, match="requires Apple Container"):
        command._container_executable()  # noqa: SLF001 -- verifies adapter-local runtime availability mapping.


def test_load_image_metadata_maps_missing_package_data_to_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_package_data(_package: str) -> object:
        raise ModuleNotFoundError

    monkeypatch.setattr(command, "files", missing_package_data)

    with pytest.raises(AppleContainerUnavailableError, match="could not be read"):
        command._load_image_metadata()  # noqa: SLF001 -- verifies adapter-local package-data failure mapping.


def test_image_inspection_maps_container_failures_to_a_stable_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, ("container", "image", "inspect"))

    monkeypatch.setattr(command.subprocess, "run", failed_run)
    monkeypatch.setattr(
        command,
        "_load_image_metadata",
        lambda: {"reference": "fabrica/workspace-search:15.2.0", "digest": "sha256:" + "0" * 64},
    )
    monkeypatch.setattr(command, "_container_executable", lambda: "/usr/local/bin/container")

    with pytest.raises(AppleContainerUnavailableError, match="unavailable"):
        verified_apple_container_search_image()


def _allow_supported_verified_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(command.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(command.platform, "mac_ver", lambda: ("26.0.0", ("", "", ""), ""))
    monkeypatch.setattr(command, "_container_executable", lambda: "/usr/local/bin/container")
    monkeypatch.setattr(
        command,
        "verified_apple_container_search_image",
        lambda: command.AppleContainerSearchImage(
            reference="fabrica/workspace-search:15.2.0", digest="sha256:" + "0" * 64
        ),
    )
