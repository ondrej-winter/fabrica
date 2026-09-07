"""Tests for the pinned-ripgrep workspace-search backend adapter."""

import asyncio
import signal
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep import adapter
from fabrica.features.workspace_searching.application.dtos import (
    SearchErrorCode,
    SearchLimits,
    SearchQuery,
    SearchQueryFailure,
    SearchQuerySuccess,
)
from fabrica.features.workspace_searching.application.ports import WorkspaceSearchContext

EXPECTED_MATCH_LINE = 2
EXPECTED_MATCH_COLUMN = 7


@dataclass(frozen=True, slots=True)
class NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Cancelled:
    @property
    def is_cancelled(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class FakeRunner:
    completed: adapter.PinnedRipgrepCommandResult | Exception
    received: tuple[str, ...] | None = None

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        cancellation: object,  # noqa: ARG002
        timeout_seconds: float,  # noqa: ARG002
        max_matching_lines: int,  # noqa: ARG002
    ) -> adapter.PinnedRipgrepCommandResult:
        object.__setattr__(self, "received", argv)
        if isinstance(self.completed, Exception):
            raise self.completed
        return self.completed


@dataclass(frozen=True, slots=True)
class FakeSourceLoader:
    source_text_by_path: dict[str, str]

    async def load(self, workspace_root: Path, paths: tuple[str, ...]) -> dict[str, str]:  # noqa: ARG002
        return {path: self.source_text_by_path[path] for path in paths}


class FakeStream:
    """Async byte stream with preconfigured line or complete-read outcomes."""

    def __init__(self, lines: tuple[bytes, ...] = (), complete: bytes = b"") -> None:
        self._lines = list(lines)
        self._complete = complete

    async def readline(self) -> bytes:
        """Return the next configured stdout line."""
        return self._lines.pop(0) if self._lines else b""

    async def read(self) -> bytes:
        """Return the configured stderr stream content."""
        return self._complete


class FakeProcess:
    """Minimal async subprocess fake for lifecycle supervision tests."""

    def __init__(self, stdout_lines: tuple[bytes, ...], *, stderr: bytes = b"", returncode: int | None = 0) -> None:
        self.stdout = FakeStream(stdout_lines)
        self.stderr = FakeStream(complete=stderr)
        self.returncode = returncode
        self.pid = 123
        self.terminated = False
        self.killed = False

    async def wait(self) -> int | None:
        """Return the preconfigured completion state."""
        return self.returncode

    def terminate(self) -> None:
        """Record direct process termination on macOS."""
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        """Record forced direct process termination on macOS."""
        self.killed = True
        self.returncode = -9


class MissingStreamProcess(FakeProcess):
    """Process fake that violates the required output-stream contract."""

    def __init__(self) -> None:
        super().__init__(())
        self.stdout = None


class DelayedFirstLineStream(FakeStream):
    """Stream that times out once before yielding its configured output."""

    def __init__(self, line: bytes) -> None:
        super().__init__((line,))
        self._first_read = True

    async def readline(self) -> bytes:
        """Delay only the first read long enough for the polling timeout."""
        if self._first_read:
            self._first_read = False
            await asyncio.sleep(1)
        return await super().readline()


class TerminationTimeoutProcess(FakeProcess):
    """Active process that requires a forced kill after one wait timeout."""

    def __init__(self) -> None:
        super().__init__((), returncode=None)
        self._wait_calls = 0

    async def wait(self) -> int | None:
        """Delay the first wait and complete immediately after forced cleanup."""
        self._wait_calls += 1
        if self._wait_calls == 1:
            await asyncio.sleep(2)
        return self.returncode

    def terminate(self) -> None:
        """Record graceful termination while keeping the fake process active."""
        self.terminated = True


class CompletedButSlowWaitProcess(FakeProcess):
    """Completed process whose delayed reap reaches no-op forced cleanup."""

    async def wait(self) -> int | None:
        """Delay the first reap beyond the termination grace period."""
        await asyncio.sleep(2)
        return self.returncode


def test_backend_returns_hydrated_matches_from_incremental_json_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _allow_command_builder(monkeypatch)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "example.py").write_text("before\nclass UserService:\nafter\n", encoding="utf-8")
    runner = FakeRunner(
        adapter.PinnedRipgrepCommandResult(
            returncode=0,
            stdout=(
                '{"type":"match","data":{"path":{"text":"src/example.py"},"line_number":2,'
                '"submatches":[{"match":{"text":"UserService"},"start":6,"end":17}]}}\n'
            ),
            stderr="",
        )
    )
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(
        tmp_path,
        command_runner=runner,
        source_loader=FakeSourceLoader({"src/example.py": "before\nclass UserService:\nafter\n"}),
    )

    result = asyncio.run(backend.search_query(SearchQuery("UserService", path="src"), _context()))

    assert isinstance(result, SearchQuerySuccess)
    assert result.matches[0].path == "src/example.py"
    assert result.matches[0].line == EXPECTED_MATCH_LINE
    assert result.matches[0].column == EXPECTED_MATCH_COLUMN
    assert result.matches[0].before[0].text == "before"
    assert result.matches[0].after[0].text == "after"
    assert runner.received is not None


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("regex parse error:\n    (", SearchErrorCode.INVALID_REGEX),
        ("error parsing glob '**/[': unclosed character class", SearchErrorCode.INVALID_GLOB),
    ],
)
def test_backend_maps_deterministic_ripgrep_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stderr: str, expected: SearchErrorCode
) -> None:
    _allow_command_builder(monkeypatch)
    runner = FakeRunner(adapter.PinnedRipgrepCommandResult(returncode=2, stdout="", stderr=stderr))
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(tmp_path, command_runner=runner)

    result = asyncio.run(backend.search_query(SearchQuery("needle"), _context()))

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is expected


@pytest.mark.parametrize(
    ("runner_error", "expected"),
    [(TimeoutError(), SearchErrorCode.SEARCH_TIMEOUT), (OSError(), SearchErrorCode.IO_ERROR)],
)
def test_backend_maps_process_failures_to_stable_outcomes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner_error: Exception, expected: SearchErrorCode
) -> None:
    _allow_command_builder(monkeypatch)
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(tmp_path, command_runner=FakeRunner(runner_error))

    result = asyncio.run(backend.search_query(SearchQuery("needle"), _context()))

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is expected
    assert result.error.metadata == ({"transient": True} if expected is SearchErrorCode.IO_ERROR else {})


def test_backend_rejects_cancelled_queries_without_launching_a_process(tmp_path: Path) -> None:
    runner = FakeRunner(adapter.PinnedRipgrepCommandResult(returncode=0, stdout="", stderr=""))
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(tmp_path, command_runner=runner)

    result = asyncio.run(backend.search_query(SearchQuery("needle"), _context(Cancelled())))

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.SEARCH_CANCELLED
    assert runner.received is None


def test_backend_preserves_search_scope_rejection_codes(tmp_path: Path) -> None:
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(tmp_path)

    result = asyncio.run(backend.search_query(SearchQuery("needle", path="missing.py"), _context()))

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.NOT_FOUND
    assert result.error.metadata == {}


def test_backend_maps_an_unavailable_pinned_ripgrep_binary_to_a_stable_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def unavailable_command(*args: object, **kwargs: object) -> tuple[str, ...]:
        del args, kwargs
        message = "unavailable"
        raise adapter.PinnedRipgrepUnavailableError(message)

    monkeypatch.setattr(adapter.PinnedRipgrepCommandBuilder, "command_for", unavailable_command)
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(tmp_path)

    result = asyncio.run(backend.search_query(SearchQuery("needle"), _context()))

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.SEARCH_BACKEND_UNAVAILABLE
    assert result.error.metadata == {}


def test_backend_maps_malformed_backend_events_to_a_transient_io_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _allow_command_builder(monkeypatch)
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(
        tmp_path,
        command_runner=FakeRunner(adapter.PinnedRipgrepCommandResult(returncode=0, stdout="not json\n", stderr="")),
    )

    result = asyncio.run(backend.search_query(SearchQuery("needle"), _context()))

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.IO_ERROR
    assert result.error.metadata == {"transient": True}


def test_backend_fails_closed_when_the_contained_backend_aborts_before_emitting_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _allow_command_builder(monkeypatch)
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(
        tmp_path,
        command_runner=FakeRunner(adapter.PinnedRipgrepCommandResult(returncode=-6, stdout="", stderr="")),
    )

    result = asyncio.run(backend.search_query(SearchQuery("needle"), _context()))

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.SEARCH_BACKEND_UNAVAILABLE


def test_backend_maps_unclassified_nonzero_backend_status_to_transient_io_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _allow_command_builder(monkeypatch)
    backend = adapter.PinnedRipgrepWorkspaceSearchBackend(
        tmp_path,
        command_runner=FakeRunner(
            adapter.PinnedRipgrepCommandResult(returncode=2, stdout="", stderr="unexpected failure")
        ),
    )

    result = asyncio.run(backend.search_query(SearchQuery("needle"), _context()))

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.IO_ERROR
    assert result.error.metadata == {"transient": True}


def test_async_runner_streams_events_and_collects_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess((b'{"type":"match"}\n', b'{"type":"summary"}\n'), stderr=b"diagnostic")
    _install_process(monkeypatch, process)

    result = asyncio.run(
        adapter.AsyncioPinnedRipgrepCommandRunner().run(
            ("verified-rg",),
            cancellation=NeverCancelled(),
            timeout_seconds=1,
            max_matching_lines=2,
        )
    )

    assert result.returncode == 0
    assert result.stdout == '{"type":"match"}\n{"type":"summary"}'
    assert result.stderr == "diagnostic"
    assert result.limit_reached is False


def test_async_runner_terminates_process_after_the_matching_line_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess((b'{"type":"match"}\n',), returncode=None)
    _install_process(monkeypatch, process)

    result = asyncio.run(
        adapter.AsyncioPinnedRipgrepCommandRunner().run(
            ("verified-rg",),
            cancellation=NeverCancelled(),
            timeout_seconds=1,
            max_matching_lines=1,
        )
    )

    assert result.limit_reached is True
    assert process.terminated is True


def test_async_runner_cleans_up_when_cancellation_is_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess((), returncode=None)
    _install_process(monkeypatch, process)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            adapter.AsyncioPinnedRipgrepCommandRunner().run(
                ("verified-rg",),
                cancellation=Cancelled(),
                timeout_seconds=1,
                max_matching_lines=1,
            )
        )

    assert process.terminated is True


def test_async_runner_times_out_and_cleans_up_the_active_process(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess((), returncode=None)
    _install_process(monkeypatch, process)
    timestamps = iter((0.0, 2.0))
    monkeypatch.setattr(adapter, "monotonic", lambda: next(timestamps))

    with pytest.raises(TimeoutError):
        asyncio.run(
            adapter.AsyncioPinnedRipgrepCommandRunner().run(
                ("verified-rg",),
                cancellation=NeverCancelled(),
                timeout_seconds=1,
                max_matching_lines=1,
            )
        )

    assert process.terminated is True


def test_async_runner_rejects_missing_output_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    process = MissingStreamProcess()
    _install_process(monkeypatch, process)

    with pytest.raises(OSError, match="output streams"):
        asyncio.run(
            adapter.AsyncioPinnedRipgrepCommandRunner().run(
                ("verified-rg",),
                cancellation=NeverCancelled(),
                timeout_seconds=1,
                max_matching_lines=1,
            )
        )


def test_async_runner_retries_after_a_short_stdout_poll_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess(())
    process.stdout = DelayedFirstLineStream(b'{"type":"summary"}\n')
    _install_process(monkeypatch, process)

    result = asyncio.run(
        adapter.AsyncioPinnedRipgrepCommandRunner().run(
            ("verified-rg",),
            cancellation=NeverCancelled(),
            timeout_seconds=1,
            max_matching_lines=1,
        )
    )

    assert result.stdout == '{"type":"summary"}'


def test_async_runner_uses_a_linux_process_group_for_cap_termination(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess((b'{"type":"match"}\n',), returncode=None)
    received_signals: list[signal.Signals] = []
    _install_process(monkeypatch, process)
    monkeypatch.setattr(adapter.sys, "platform", "linux")
    monkeypatch.setattr(adapter.os, "killpg", lambda _pid, sent_signal: received_signals.append(sent_signal))

    result = asyncio.run(
        adapter.AsyncioPinnedRipgrepCommandRunner().run(
            ("verified-rg",),
            cancellation=NeverCancelled(),
            timeout_seconds=1,
            max_matching_lines=1,
        )
    )

    assert result.limit_reached is True
    assert received_signals == [signal.SIGTERM]


def test_async_runner_force_kills_a_timed_out_linux_process_group(monkeypatch: pytest.MonkeyPatch) -> None:
    process = TerminationTimeoutProcess()
    received_signals: list[signal.Signals] = []
    _install_process(monkeypatch, process)
    monkeypatch.setattr(adapter.sys, "platform", "linux")
    monkeypatch.setattr(adapter.os, "killpg", lambda _pid, sent_signal: received_signals.append(sent_signal))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            adapter.AsyncioPinnedRipgrepCommandRunner().run(
                ("verified-rg",),
                cancellation=Cancelled(),
                timeout_seconds=1,
                max_matching_lines=1,
            )
        )

    assert received_signals == [signal.SIGTERM, signal.SIGKILL]


def test_async_runner_force_kills_a_timed_out_macos_process(monkeypatch: pytest.MonkeyPatch) -> None:
    process = TerminationTimeoutProcess()
    _install_process(monkeypatch, process)
    monkeypatch.setattr(adapter.sys, "platform", "darwin")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            adapter.AsyncioPinnedRipgrepCommandRunner().run(
                ("verified-rg",),
                cancellation=Cancelled(),
                timeout_seconds=1,
                max_matching_lines=1,
            )
        )

    assert process.terminated is True
    assert process.killed is True


def test_async_runner_does_not_signal_an_already_completed_linux_process(monkeypatch: pytest.MonkeyPatch) -> None:
    process = CompletedButSlowWaitProcess(())
    received_signals: list[signal.Signals] = []
    _install_process(monkeypatch, process)
    monkeypatch.setattr(adapter.sys, "platform", "linux")
    monkeypatch.setattr(adapter.os, "killpg", lambda _pid, sent_signal: received_signals.append(sent_signal))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            adapter.AsyncioPinnedRipgrepCommandRunner().run(
                ("verified-rg",),
                cancellation=Cancelled(),
                timeout_seconds=1,
                max_matching_lines=1,
            )
        )

    assert received_signals == []


def test_posix_source_loader_reads_workspace_relative_utf8_source(tmp_path: Path) -> None:
    source_file = tmp_path / "src" / "example.py"
    source_file.parent.mkdir()
    source_file.write_text("example\r\n", encoding="utf-8")

    loaded = asyncio.run(adapter.PosixWorkspaceSourceLoader().load(tmp_path, ("src/example.py",)))

    assert loaded == {"src/example.py": "example\n"}


def test_posix_source_loader_rejects_a_path_outside_the_workspace(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside.py"
    outside_file.write_text("outside", encoding="utf-8")
    (tmp_path / "linked.py").symlink_to(outside_file)

    with pytest.raises(OSError, match="unavailable"):
        asyncio.run(adapter.PosixWorkspaceSourceLoader().load(tmp_path, ("linked.py",)))


def _install_process(monkeypatch: pytest.MonkeyPatch, process: FakeProcess) -> None:
    async def create_process(*_args: object, **_kwargs: object) -> FakeProcess:
        return process

    monkeypatch.setattr(adapter.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(adapter.os, "killpg", lambda _pid, _signal: process.terminate())


def _allow_command_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        adapter.PinnedRipgrepCommandBuilder,
        "command_for",
        lambda _self, _query, scope, _limits: ("verified-rg", "--json", str(scope.canonical_path)),
    )


def _context(cancellation: NeverCancelled | Cancelled | None = None) -> WorkspaceSearchContext:
    return WorkspaceSearchContext(
        cancellation=cancellation or NeverCancelled(),
        deadline_at=datetime.now(UTC) + timedelta(seconds=5),
        limits=SearchLimits(),
    )
