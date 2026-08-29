"""Pinned-ripgrep implementation of the workspace-searching outbound port."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from contextlib import suppress
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING, Protocol

from fabrica.features.workspace_searching.adapters.outbound.apple_container import AppleContainerUnavailableError
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.command import PinnedRipgrepCommandBuilder
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.json_parser import (
    RipgrepJsonEventError,
    parse_ripgrep_json_events,
)
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import PinnedRipgrepUnavailableError
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import (
    SearchSandboxUnavailableError,
    SearchScopeResolutionError,
    resolve_search_scope,
)
from fabrica.features.workspace_searching.application.context_hydration import hydrate_search_locations
from fabrica.features.workspace_searching.application.dtos import (
    SearchError,
    SearchErrorCode,
    SearchQuery,
    SearchQueryFailure,
    SearchQueryResult,
    SearchQuerySuccess,
)
from fabrica.features.workspace_searching.application.ports import WorkspaceSearchBackend, WorkspaceSearchContext

if TYPE_CHECKING:
    from pathlib import Path

_POLL_INTERVAL_SECONDS = 0.01
_PROCESS_TERMINATION_GRACE_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class PinnedRipgrepCommandResult:
    """Captured output from one completed pinned-ripgrep process group."""

    returncode: int
    stdout: str
    stderr: str
    limit_reached: bool = False


class PinnedRipgrepCommandRunner(Protocol):
    """Lifecycle boundary for one sandboxed pinned-ripgrep invocation."""

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        cancellation: object,
        timeout_seconds: float,
        max_matching_lines: int,
    ) -> PinnedRipgrepCommandResult:
        """Run one command and clean up its process group before returning."""
        ...


class WorkspaceSourceLoader(Protocol):
    """Adapter-local source loading boundary used for context hydration."""

    async def load(self, workspace_root: Path, paths: tuple[str, ...]) -> dict[str, str]:
        """Asynchronously load UTF-8 source text for contained workspace-relative paths."""
        ...


@dataclass(frozen=True, slots=True)
class AsyncioPinnedRipgrepCommandRunner:
    """Execute explicit sandboxed argv values in a dedicated process session."""

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        cancellation: object,
        timeout_seconds: float,
        max_matching_lines: int,
    ) -> PinnedRipgrepCommandResult:
        """Run one process group while observing cancellation and timeout bounds."""
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=sys.platform != "darwin",
        )
        if process.stdout is None or process.stderr is None:
            msg = "pinned ripgrep process did not expose output streams"
            await _terminate_process_group(process)
            raise OSError(msg)
        stderr_task = asyncio.create_task(process.stderr.read())
        deadline = monotonic() + timeout_seconds
        output_events: list[str] = []
        matching_lines = 0
        limit_reached = False
        try:
            while True:
                if _is_cancelled(cancellation):
                    _raise_cancelled()
                if monotonic() >= deadline:
                    _raise_timeout()
                try:
                    output = await asyncio.wait_for(process.stdout.readline(), timeout=_POLL_INTERVAL_SECONDS)
                except TimeoutError:
                    continue
                if not output:
                    break
                event = output.decode("utf-8", errors="replace").rstrip("\n")
                output_events.append(event)
                if _is_match_event(event):
                    matching_lines += 1
                    if matching_lines >= max_matching_lines:
                        limit_reached = True
                        await _terminate_process_group(process)
                        break
            await process.wait()
            stderr = (await stderr_task).decode("utf-8", errors="replace")
        except BaseException:
            await _terminate_process_group(process)
            await asyncio.gather(stderr_task, return_exceptions=True)
            raise
        return PinnedRipgrepCommandResult(
            returncode=process.returncode if process.returncode is not None else -1,
            stdout="\n".join(output_events),
            stderr=stderr,
            limit_reached=limit_reached,
        )


@dataclass(frozen=True, slots=True)
class PosixWorkspaceSourceLoader:
    """Load matched source files after enforcing their workspace containment."""

    async def load(self, workspace_root: Path, paths: tuple[str, ...]) -> dict[str, str]:
        """Load source text without blocking cancellation supervision on the event loop."""
        return await asyncio.to_thread(_load_source_text, workspace_root, paths)


def _load_source_text(workspace_root: Path, paths: tuple[str, ...]) -> dict[str, str]:
    """Return newline-normalized UTF-8 source text for requested paths."""
    root = workspace_root.resolve(strict=True)
    source_text_by_path: dict[str, str] = {}
    for path in paths:
        candidate = root / path
        canonical_path = candidate.resolve(strict=True)
        if not canonical_path.is_relative_to(root) or not canonical_path.is_file():
            msg = "matched source path is unavailable inside the workspace"
            raise OSError(msg)
        source_text_by_path[path] = canonical_path.read_text(encoding="utf-8-sig", newline=None)
    return source_text_by_path


@dataclass(frozen=True, slots=True)
class PinnedRipgrepWorkspaceSearchBackend(WorkspaceSearchBackend):
    """Search one contained scope using only the checksum-verified ripgrep binary."""

    workspace_root: Path
    command_runner: PinnedRipgrepCommandRunner = AsyncioPinnedRipgrepCommandRunner()
    source_loader: WorkspaceSourceLoader = PosixWorkspaceSourceLoader()

    async def search_query(self, query: SearchQuery, context: WorkspaceSearchContext) -> SearchQueryResult:
        """Execute and hydrate one query into its canonical stable outcome."""
        if _is_cancelled(context.cancellation):
            return _failure(query, SearchErrorCode.SEARCH_CANCELLED)
        try:
            scope = resolve_search_scope(self.workspace_root, query.path)
            command = PinnedRipgrepCommandBuilder(self.workspace_root).command_for(query, scope, context.limits)
            completed = await self.command_runner.run(
                command,
                cancellation=context.cancellation,
                timeout_seconds=context.limits.per_query_timeout_seconds,
                max_matching_lines=context.limits.max_results_per_query,
            )
            return await self._result_from_completed(query, completed, context)
        except SearchScopeResolutionError as err:
            result = _failure(query, err.code)
        except (AppleContainerUnavailableError, PinnedRipgrepUnavailableError, SearchSandboxUnavailableError):
            result = _failure(query, SearchErrorCode.SEARCH_BACKEND_UNAVAILABLE)
        except asyncio.CancelledError:
            result = _failure(query, SearchErrorCode.SEARCH_CANCELLED)
        except TimeoutError:
            result = _failure(query, SearchErrorCode.SEARCH_TIMEOUT)
        except OSError:
            result = _failure(query, SearchErrorCode.IO_ERROR, transient=True)
        else:
            msg = "search result processing completed without returning an outcome"
            raise RuntimeError(msg)
        return result

    async def _result_from_completed(
        self,
        query: SearchQuery,
        completed: PinnedRipgrepCommandResult,
        context: WorkspaceSearchContext,
    ) -> SearchQueryResult:
        """Map completed backend output into a cancellation-aware canonical result."""
        diagnostic_code = _diagnostic_error_code(completed.stderr)
        if diagnostic_code is not None:
            return _failure(query, diagnostic_code)
        if completed.returncode < 0 and not completed.stdout and not completed.stderr:
            return _failure(query, SearchErrorCode.SEARCH_BACKEND_UNAVAILABLE)
        if completed.returncode not in {0, 1} and not completed.limit_reached:
            return _failure(query, SearchErrorCode.IO_ERROR, transient=True)
        try:
            locations = tuple(parse_ripgrep_json_events(completed.stdout.splitlines()))
            paths = tuple(sorted({location.path for location in locations}))
            source_text_by_path = await self.source_loader.load(self.workspace_root, paths)
            matches = hydrate_search_locations(locations, source_text_by_path, limits=context.limits)
        except (RipgrepJsonEventError, UnicodeError, ValueError, OSError):
            return _failure(query, SearchErrorCode.IO_ERROR, transient=True)
        return SearchQuerySuccess(
            query=query,
            matches=matches,
            limit_reached=completed.limit_reached,
            more_results_possible=completed.limit_reached,
        )


async def _terminate_process_group(process: asyncio.subprocess.Process) -> None:
    """Terminate and reap a process session after an interrupted execution."""
    _terminate_process(process)
    try:
        await asyncio.wait_for(process.wait(), timeout=_PROCESS_TERMINATION_GRACE_SECONDS)
    except TimeoutError:
        _kill_process(process)
        await asyncio.gather(process.wait(), return_exceptions=True)


def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if sys.platform == "darwin":
        process.terminate()
        return
    if process.pid is not None:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)


def _kill_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if sys.platform == "darwin":
        process.kill()
        return
    if process.pid is not None:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)


def _is_cancelled(cancellation: object) -> bool:
    return bool(getattr(cancellation, "is_cancelled", False))


def _is_match_event(event: str) -> bool:
    return '"type":"match"' in event.replace(" ", "")


def _raise_cancelled() -> None:
    raise asyncio.CancelledError


def _raise_timeout() -> None:
    raise TimeoutError


def _diagnostic_error_code(stderr: str) -> SearchErrorCode | None:
    normalized = stderr.lower()
    if "regex parse error" in normalized:
        return SearchErrorCode.INVALID_REGEX
    if "error parsing glob" in normalized or "invalid glob" in normalized:
        return SearchErrorCode.INVALID_GLOB
    return None


def _failure(query: SearchQuery, code: SearchErrorCode, *, transient: bool = False) -> SearchQueryFailure:
    metadata = {"transient": True} if transient else {}
    return SearchQueryFailure(query=query, error=SearchError(code=code, metadata=metadata))


__all__ = [
    "AsyncioPinnedRipgrepCommandRunner",
    "PinnedRipgrepCommandResult",
    "PinnedRipgrepCommandRunner",
    "PinnedRipgrepWorkspaceSearchBackend",
    "PosixWorkspaceSourceLoader",
    "WorkspaceSourceLoader",
]
