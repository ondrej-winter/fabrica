"""Tests for workspace-editing application port import boundaries."""

import inspect

from fabrica.features.workspace_editing.application import ports


def test_workspace_editing_ports_are_application_owned_protocols_without_adapter_types() -> None:
    exported_names = set(ports.__all__)

    assert {
        "PatchApprovalRequester",
        "PatchCancellationSignal",
        "PatchClock",
        "PatchCommitter",
        "PatchJournalStore",
        "PatchMutationLeaseManager",
        "PatchPolicyEvaluator",
        "PatchRecoveryCoordinator",
        "PatchStager",
        "PatchWorkspaceSnapshotReader",
    } <= exported_names
    for name in exported_names:
        exported = getattr(ports, name)
        assert inspect.isclass(exported)
        assert "fabrica.features.workspace_editing.application.ports" in exported.__module__

    source = inspect.getsource(ports)

    assert ".adapters" not in source
    assert "os." not in source
    assert "pathlib" not in source
