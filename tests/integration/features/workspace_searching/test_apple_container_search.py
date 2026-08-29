"""Opt-in macOS Apple Container conformance for the search image payload."""

import asyncio
import os
import platform
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import PinnedRipgrepWorkspaceSearchBackend
from fabrica.features.workspace_searching.application.dtos import SearchLimits, SearchQuery, SearchQuerySuccess
from fabrica.features.workspace_searching.application.ports import WorkspaceSearchContext

_ENABLE_ENVIRONMENT_VARIABLE = "FABRICA_APPLE_CONTAINER_SEARCH_CONFORMANCE"

pytestmark = pytest.mark.skipif(
    os.environ.get(_ENABLE_ENVIRONMENT_VARIABLE) != "1"
    or platform.system() != "Darwin"
    or platform.machine() not in {"arm64", "aarch64"},
    reason=(
        "set FABRICA_APPLE_CONTAINER_SEARCH_CONFORMANCE=1 on macOS Apple Silicon "
        "after provisioning the Fabrica OCI image"
    ),
)


def test_apple_container_searches_a_read_only_workspace_fixture(tmp_path: Path) -> None:
    source_file = tmp_path / "source.py"
    source_file.write_text("needle = 1\n", encoding="utf-8")
    context = WorkspaceSearchContext(
        cancellation=_NeverCancelled(),
        deadline_at=datetime.now(UTC) + timedelta(seconds=10),
        limits=SearchLimits(),
    )

    result = asyncio.run(PinnedRipgrepWorkspaceSearchBackend(tmp_path).search_query(SearchQuery("needle"), context))

    assert isinstance(result, SearchQuerySuccess)
    assert [(match.path, match.line) for match in result.matches] == [("source.py", 1)]


class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False
