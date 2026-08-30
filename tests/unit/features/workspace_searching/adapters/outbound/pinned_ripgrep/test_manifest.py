"""Tests for pinned-ripgrep package-data selection and integrity checks."""

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import manifest
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import (
    PinnedRipgrepUnavailableError,
    verified_pinned_ripgrep_executable,
)


def test_verified_pinned_ripgrep_executable_selects_an_executable_with_expected_version() -> None:
    executable = verified_pinned_ripgrep_executable()

    assert executable.version == "15.2.0"
    assert executable.path.is_file()
    assert executable.path.stat().st_mode & 0o111
    assert executable.platform_key in {"darwin-arm64", "linux-x86_64"}


def test_verified_pinned_ripgrep_executable_fails_closed_on_an_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manifest.platform, "system", lambda: "Windows")
    monkeypatch.setattr(manifest.platform, "machine", lambda: "AMD64")

    with pytest.raises(PinnedRipgrepUnavailableError, match="unavailable"):
        verified_pinned_ripgrep_executable()


def test_verified_pinned_ripgrep_executable_rejects_checksum_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        manifest,
        "_load_manifest",
        lambda: {"version": "15.2.0", "artifacts": {"darwin-arm64": {"path": "macos_arm64/rg", "sha256": "0" * 64}}},
    )
    monkeypatch.setattr(manifest, "_platform_key", lambda: "darwin-arm64")

    with pytest.raises(PinnedRipgrepUnavailableError, match="checksum"):
        verified_pinned_ripgrep_executable()


@pytest.mark.parametrize(
    "invalid_manifest",
    [
        {"version": "not-15.2.0", "artifacts": {}},
        {"version": "15.2.0", "artifacts": []},
        {"version": "15.2.0", "artifacts": {"darwin-arm64": []}},
        {"version": "15.2.0", "artifacts": {"darwin-arm64": {}}},
    ],
)
def test_verified_pinned_ripgrep_executable_rejects_malformed_manifest_entries(
    monkeypatch: pytest.MonkeyPatch,
    invalid_manifest: dict[str, object],
) -> None:
    monkeypatch.setattr(manifest, "_load_manifest", lambda: invalid_manifest)
    monkeypatch.setattr(manifest, "_platform_key", lambda: "darwin-arm64")

    with pytest.raises(PinnedRipgrepUnavailableError):
        verified_pinned_ripgrep_executable()


def test_verified_pinned_ripgrep_executable_rejects_a_missing_platform_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manifest, "_load_manifest", lambda: {"version": "15.2.0", "artifacts": {}})
    monkeypatch.setattr(manifest, "_platform_key", lambda: "darwin-arm64")

    with pytest.raises(PinnedRipgrepUnavailableError, match="unavailable"):
        verified_pinned_ripgrep_executable()


def test_load_manifest_maps_invalid_package_data_to_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    class _InvalidManifestResource:
        def read_text(self, *, encoding: str) -> str:  # noqa: ARG002 - resource protocol shape.
            return "not JSON"

    class _PackageResource:
        def joinpath(self, name: str) -> _InvalidManifestResource:  # noqa: ARG002 - manifest is fixed.
            return _InvalidManifestResource()

    monkeypatch.setattr(manifest, "files", lambda _package: _PackageResource())

    with pytest.raises(PinnedRipgrepUnavailableError, match="could not be read"):
        verified_pinned_ripgrep_executable()
