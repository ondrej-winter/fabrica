"""Pinned ripgrep package-data verification and JSON event translation."""

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.adapter import (
    AsyncioPinnedRipgrepCommandRunner,
    PinnedRipgrepCommandResult,
    PinnedRipgrepWorkspaceSearchBackend,
    PosixWorkspaceSourceLoader,
)
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.command import build_pinned_ripgrep_command
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.json_parser import (
    RipgrepJsonEventError,
    parse_ripgrep_json_events,
)
from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import (
    PinnedRipgrepUnavailableError,
    verified_pinned_ripgrep_executable,
)

__all__ = [
    "AsyncioPinnedRipgrepCommandRunner",
    "PinnedRipgrepCommandResult",
    "PinnedRipgrepUnavailableError",
    "PinnedRipgrepWorkspaceSearchBackend",
    "PosixWorkspaceSourceLoader",
    "RipgrepJsonEventError",
    "build_pinned_ripgrep_command",
    "parse_ripgrep_json_events",
    "verified_pinned_ripgrep_executable",
]
