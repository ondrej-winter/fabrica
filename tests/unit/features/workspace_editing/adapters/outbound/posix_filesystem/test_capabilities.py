"""Tests for fail-closed POSIX production capability evidence."""

import sys
from pathlib import Path

import pytest

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import capabilities
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.capabilities import (
    PosixPatchCapabilityProbe,
    PosixPatchCapabilityStatus,
    PosixPatchWorkspaceCapabilityEvidence,
    collect_posix_patch_workspace_capability_evidence,
)


def test_capability_evidence_requires_every_probe_to_succeed() -> None:
    evidence = PosixPatchWorkspaceCapabilityEvidence(
        platform="darwin",
        machine="arm64",
        workspace_device=1,
        filesystem_type="apfs",
        backend="darwin_renameatx_np_supervised_helper_v1",
        probes=(
            PosixPatchCapabilityProbe("native_no_replace", PosixPatchCapabilityStatus.SUPPORTED, "proven"),
            PosixPatchCapabilityProbe("helper", PosixPatchCapabilityStatus.SUPPORTED, "proven"),
        ),
    )

    assert evidence.production_ready is True
    assert evidence.unsupported_reasons == ()


def test_capability_evidence_reports_unsupported_and_failed_probe_names() -> None:
    evidence = PosixPatchWorkspaceCapabilityEvidence(
        platform="linux",
        machine="x86_64",
        workspace_device=2,
        filesystem_type="ext4",
        backend="linux_renameat2_supervised_helper_v1",
        probes=(
            PosixPatchCapabilityProbe("native_no_replace", PosixPatchCapabilityStatus.UNSUPPORTED, "not proven"),
            PosixPatchCapabilityProbe("workspace_root", PosixPatchCapabilityStatus.FAILED, "errno=13"),
        ),
    )

    assert evidence.production_ready is False
    assert evidence.unsupported_reasons == ("native_no_replace", "workspace_root")


def test_collecting_current_workspace_evidence_reports_supervised_helper_ownership(
    tmp_path: Path,
) -> None:
    evidence = collect_posix_patch_workspace_capability_evidence(tmp_path)

    assert evidence.workspace_device == tmp_path.stat().st_dev
    assert evidence.backend
    helper_probe = next(probe for probe in evidence.probes if probe.name == "supervised_helper_ownership")
    assert helper_probe.status is PosixPatchCapabilityStatus.SUPPORTED
    if sys.platform == "darwin":
        native_probe = next(probe for probe in evidence.probes if probe.name == "native_no_replace")
        assert native_probe.status is PosixPatchCapabilityStatus.SUPPORTED


def test_helper_ownership_probe_rejects_hosts_without_supervision_primitives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capabilities, "supervised_helper_ownership_available", lambda: False)

    evidence = collect_posix_patch_workspace_capability_evidence(tmp_path)

    helper_probe = next(probe for probe in evidence.probes if probe.name == "supervised_helper_ownership")
    assert helper_probe.status is PosixPatchCapabilityStatus.UNSUPPORTED
    assert "supervised_helper_ownership" in evidence.unsupported_reasons


def test_collecting_missing_workspace_reports_a_failed_root_probe(tmp_path: Path) -> None:
    missing_workspace = tmp_path / "missing"

    evidence = collect_posix_patch_workspace_capability_evidence(missing_workspace)

    assert evidence.production_ready is False
    assert evidence.workspace_device is None
    assert evidence.probes[0].name == "workspace_root"
    assert evidence.probes[0].status is PosixPatchCapabilityStatus.FAILED


def test_directory_descriptor_probe_failure_is_captured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_open(*_args: object, **_kwargs: object) -> int:
        raise OSError(13, "denied")

    monkeypatch.setattr(capabilities.os, "open", fail_open)

    evidence = collect_posix_patch_workspace_capability_evidence(tmp_path)

    probe = next(probe for probe in evidence.probes if probe.name == "descriptor_rooted_traversal")
    assert probe.status is PosixPatchCapabilityStatus.FAILED
    assert probe.detail == "PermissionError: errno=13"


def test_platform_specific_probe_selection_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capabilities.sys, "platform", "linux")
    monkeypatch.setattr(capabilities, "native_no_replace_backend_available", lambda: True)
    monkeypatch.setattr(capabilities, "prove_native_no_replace", lambda _workspace_root: None)

    linux_evidence = collect_posix_patch_workspace_capability_evidence(Path.cwd())

    assert linux_evidence.backend == "linux_renameat2_supervised_helper_v1"
    assert next(probe for probe in linux_evidence.probes if probe.name == "platform_scope").status is (
        PosixPatchCapabilityStatus.SUPPORTED
    )
    assert "native_no_replace" not in linux_evidence.unsupported_reasons

    monkeypatch.setattr(capabilities.sys, "platform", "freebsd")
    monkeypatch.setattr(capabilities, "native_no_replace_backend_available", lambda: False)

    unsupported_evidence = collect_posix_patch_workspace_capability_evidence(Path.cwd())

    assert unsupported_evidence.backend == "unselected"
    assert "platform_scope" in unsupported_evidence.unsupported_reasons
    assert "native_no_replace" in unsupported_evidence.unsupported_reasons


def test_platform_scope_rejects_non_apple_silicon_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capabilities.sys, "platform", "darwin")
    monkeypatch.setattr(capabilities.platform, "machine", lambda: "x86_64")

    evidence = collect_posix_patch_workspace_capability_evidence(Path.cwd())
    probe = next(probe for probe in evidence.probes if probe.name == "platform_scope")

    assert probe.status is PosixPatchCapabilityStatus.UNSUPPORTED


def test_descriptor_and_no_follow_probes_reject_missing_python_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(capabilities.os, "O_DIRECTORY")
    monkeypatch.delattr(capabilities.os, "O_NOFOLLOW")

    evidence = collect_posix_patch_workspace_capability_evidence(tmp_path)
    descriptor_probe = next(probe for probe in evidence.probes if probe.name == "descriptor_rooted_traversal")
    no_follow_probe = next(probe for probe in evidence.probes if probe.name == "no_follow_path_resolution")

    assert descriptor_probe.status is PosixPatchCapabilityStatus.UNSUPPORTED
    assert no_follow_probe.status is PosixPatchCapabilityStatus.UNSUPPORTED


def test_filesystem_type_is_unknown_when_stat_command_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capabilities.sys, "platform", "darwin")

    def fail_stat(*_args: object, **_kwargs: object) -> None:
        raise OSError(2, "not found")

    monkeypatch.setattr(capabilities.subprocess, "run", fail_stat)

    evidence = collect_posix_patch_workspace_capability_evidence(tmp_path)
    assert evidence.filesystem_type == "unknown"

    monkeypatch.setattr(capabilities.sys, "platform", "freebsd")

    unsupported_evidence = collect_posix_patch_workspace_capability_evidence(tmp_path)
    assert unsupported_evidence.filesystem_type == "unsupported-platform"
