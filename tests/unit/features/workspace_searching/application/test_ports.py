"""Tests for workspace-searching application port ownership."""

import inspect
from datetime import UTC, datetime

import pytest

from fabrica.features.workspace_searching.application import ports
from fabrica.features.workspace_searching.application.dtos import SearchLimits
from fabrica.features.workspace_searching.application.ports import WorkspaceSearchContext


class NeverCancelled:
    """Test cancellation signal that never requests cancellation."""

    @property
    def is_cancelled(self) -> bool:
        return False


def test_workspace_searching_ports_are_application_owned_without_adapter_types() -> None:
    exported_names = set(ports.__all__)

    assert {
        "SearchCodebasePort",
        "WorkspaceSearchBackend",
        "WorkspaceSearchCancellationSignal",
        "WorkspaceSearchContext",
    } <= exported_names
    for name in exported_names:
        exported = getattr(ports, name)
        assert inspect.isclass(exported)
        assert "fabrica.features.workspace_searching.application.ports" in exported.__module__

    source = inspect.getsource(ports)
    assert ".adapters" not in source
    assert "pathlib" not in source
    assert "open(" not in source


def test_workspace_search_context_requires_an_aware_deadline() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        WorkspaceSearchContext(
            cancellation=NeverCancelled(),
            deadline_at=datetime.fromtimestamp(0, tz=UTC).replace(tzinfo=None),
            limits=SearchLimits(),
        )
