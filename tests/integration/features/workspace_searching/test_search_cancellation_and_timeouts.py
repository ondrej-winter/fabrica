"""Integration tests for workspace-search interruption and hydration cancellation."""

import asyncio
import errno
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import adapter
from fabrica.features.workspace_searching.application.dtos import (
    SearchCodebaseCommand,
    SearchErrorCode,
    SearchLimits,
    SearchQuery,
    SearchQueryFailure,
)
from fabrica.features.workspace_searching.application.ports import WorkspaceSearchContext
from fabrica.features.workspace_searching.application.use_cases import SearchCodebase

_POLL_INTERVAL_SECONDS = 0.01
_POST_START_TIMEOUT_SECONDS = 2.0

pytestmark = pytest.mark.skipif(
    sys.platform not in {"darwin", "linux"},
    reason="POSIX search adapter targets macOS/Linux",
)


class MutableCancellation:
    """Cancellation signal controlled by a test's host-side lifecycle."""

    def __init__(self) -> None:
        self.cancelled = False

    @property
    def is_cancelled(self) -> bool:
        """Return whether the test host has requested cancellation."""
        return self.cancelled


@dataclass(frozen=True, slots=True)
class CompletedRunner:
    """Return a completed backend event stream before context hydration begins."""

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        cancellation: object,
        timeout_seconds: float,
        max_matching_lines: int,
    ) -> adapter.PinnedRipgrepCommandResult:
        """Return one match event without launching a separate process."""
        del argv, cancellation, timeout_seconds, max_matching_lines
        return adapter.PinnedRipgrepCommandResult(
            returncode=0,
            stdout=(
                '{"type":"match","data":{"path":{"text":"source.py"},"line_number":1,'
                '"submatches":[{"match":{"text":"needle"},"start":0,"end":6}]}}'
            ),
            stderr="",
        )


class BlockingSourceLoader:
    """Source loader that remains in hydration until the scheduler cancels it."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def load(self, workspace_root: Path, paths: tuple[str, ...]) -> dict[str, str]:
        """Block after signaling that context hydration has begun."""
        del workspace_root, paths
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        msg = "blocking source loader unexpectedly completed"
        raise AssertionError(msg)


@pytest.mark.parametrize("interruption", ["timeout", "cancellation"])
def test_runner_terminates_a_real_subprocess_after_interruption(tmp_path: Path, interruption: str) -> None:
    """Prove timeout and cancellation terminate the active subprocess before return."""
    script_path = tmp_path / "block.py"
    started_path = tmp_path / "started"
    pid_path = tmp_path / "pid"
    script_path.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import time\n"
        "started_path = Path(__import__('sys').argv[1])\n"
        "pid_path = Path(__import__('sys').argv[2])\n"
        "pid_path.write_text(str(os.getpid()), encoding='utf-8')\n"
        "started_path.touch()\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    cancellation = MutableCancellation()

    async def run() -> None:
        task = asyncio.create_task(
            adapter.AsyncioPinnedRipgrepCommandRunner().run(
                (sys.executable, str(script_path), str(started_path), str(pid_path)),
                cancellation=cancellation,
                timeout_seconds=_POST_START_TIMEOUT_SECONDS if interruption == "timeout" else 5.0,
                max_matching_lines=1,
            )
        )
        await _wait_for_path(started_path)
        if interruption == "cancellation":
            cancellation.cancelled = True
        expected_error = TimeoutError if interruption == "timeout" else asyncio.CancelledError
        with pytest.raises(expected_error):
            await task

    asyncio.run(run())

    process_id = int(pid_path.read_text(encoding="utf-8"))
    with pytest.raises(OSError, check=lambda error: error.errno == errno.ESRCH):
        os.kill(process_id, 0)


def test_scheduler_cancellation_interrupts_blocked_context_hydration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Prove batch cancellation propagates through the adapter's hydration phase."""
    source_file = tmp_path / "source.py"
    source_file.write_text("needle\n", encoding="utf-8")
    cancellation = MutableCancellation()
    source_loader = BlockingSourceLoader()
    monkeypatch.setattr(
        adapter.PinnedRipgrepCommandBuilder,
        "command_for",
        lambda _self, _query, scope, _limits: ("verified-rg", str(scope.canonical_path)),
    )
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(
        tmp_path,
        command_runner=CompletedRunner(),
        source_loader=source_loader,
    )
    context = WorkspaceSearchContext(
        cancellation=cancellation,
        deadline_at=datetime.now(UTC) + timedelta(seconds=5),
        limits=SearchLimits(max_retries=0),
    )

    async def search() -> SearchQueryFailure:
        task = asyncio.create_task(
            SearchCodebase(backend).search(
                SearchCodebaseCommand((SearchQuery("needle"),)),
                context,
            )
        )
        await source_loader.started.wait()
        cancellation.cancelled = True
        result = await task
        outcome = result.results[0]
        assert isinstance(outcome, SearchQueryFailure)
        return outcome

    outcome = asyncio.run(search())

    assert outcome.error.code is SearchErrorCode.SEARCH_CANCELLED
    assert source_loader.cancelled is True


async def _wait_for_path(path: Path) -> None:
    """Wait briefly for a subprocess fixture to report that it has started."""
    for _ in range(100):
        if await asyncio.to_thread(path.exists):
            return
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    msg = "subprocess fixture did not report startup"
    raise TimeoutError(msg)
