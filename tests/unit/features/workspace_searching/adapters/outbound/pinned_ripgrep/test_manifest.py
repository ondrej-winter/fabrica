"""Tests for Linux pinned-ripgrep package-data integrity checks."""

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import manifest
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import (
    PinnedRipgrepUnavailableError,
    verified_linux_pinned_ripgrep_executable,
)


def test_verified_linux_pinned_ripgrep_executable_selects_an_executable_with_expected_version() -> None:
    executable = verified_linux_pinned_ripgrep_executable()

    assert executable.version == "15.2.0"
    assert executable.path.is_file()
    assert executable.path.stat().st_mode & 0o111
    assert executable.platform_key == "linux-x86_64"


def test_verified_linux_pinned_ripgrep_executable_rejects_checksum_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest._load_manifest",
        lambda: {"version": "15.2.0", "artifacts": {"linux-x86_64": {"path": "linux_x86_64/rg", "sha256": "0" * 64}}},
    )

    with pytest.raises(PinnedRipgrepUnavailableError, match="checksum"):
        verified_linux_pinned_ripgrep_executable()


@pytest.mark.parametrize(
    "invalid_manifest",
    [
        {"version": "not-15.2.0", "artifacts": {}},
        {"version": "15.2.0", "artifacts": []},
        {"version": "15.2.0", "artifacts": {"linux-x86_64": []}},
        {"version": "15.2.0", "artifacts": {"linux-x86_64": {}}},
    ],
)
def test_verified_linux_pinned_ripgrep_executable_rejects_malformed_manifest_entries(
    monkeypatch: pytest.MonkeyPatch,
    invalid_manifest: dict[str, object],
) -> None:
    monkeypatch.setattr(manifest, "_load_manifest", lambda: invalid_manifest)
    with pytest.raises(PinnedRipgrepUnavailableError):
        verified_linux_pinned_ripgrep_executable()


def test_verified_linux_pinned_ripgrep_executable_rejects_a_missing_linux_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manifest, "_load_manifest", lambda: {"version": "15.2.0", "artifacts": {}})
    with pytest.raises(PinnedRipgrepUnavailableError, match="unavailable"):
        verified_linux_pinned_ripgrep_executable()


def test_load_manifest_maps_invalid_package_data_to_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    class _InvalidManifestResource:
        def read_text(self, *, encoding: str) -> str:  # noqa: ARG002 - resource protocol shape.
            return "not JSON"

    class _PackageResource:
        def joinpath(self, name: str) -> _InvalidManifestResource:  # noqa: ARG002 - manifest is fixed.
            return _InvalidManifestResource()

    monkeypatch.setattr(manifest, "files", lambda _package: _PackageResource())
    with pytest.raises(PinnedRipgrepUnavailableError, match="could not be read"):
        verified_linux_pinned_ripgrep_executable()
