"""Build fixed direct native ripgrep commands from canonical search requests."""

from dataclasses import dataclass
from pathlib import Path

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import (
    PinnedRipgrepUnavailableError,
    verified_pinned_ripgrep_executable,
)
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import SearchScope
from fabrica.features.workspace_searching.application.dtos import SearchLimits, SearchQuery

_ALWAYS_EXCLUDED_GLOBS = ("!.git/**", "!node_modules/**")


@dataclass(frozen=True, slots=True)
class PinnedRipgrepCommandBuilder:
    """Construct one verified pinned-ripgrep command without shell interpretation."""

    workspace_root: Path

    def command_for(self, query: SearchQuery, scope: SearchScope, limits: SearchLimits) -> tuple[str, ...]:
        """Return fixed backend arguments with the validated canonical scope."""
        executable = verified_pinned_ripgrep_executable()
        backend_argv = self._backend_argv(str(executable.path), query, scope, limits)
        if executable.platform_key in {"linux-x86_64", "darwin-arm64"}:
            return (*backend_argv, str(scope.canonical_path))
        msg = "pinned ripgrep backend is unavailable for this platform"
        raise PinnedRipgrepUnavailableError(msg)

    def _backend_argv(
        self,
        executable: str,
        query: SearchQuery,
        scope: SearchScope,
        limits: SearchLimits,
    ) -> tuple[str, ...]:
        arguments = [
            executable,
            "--json",
            "--no-config",
            "--hidden",
            "--no-follow",
            "--no-ignore-parent",
            f"--max-filesize={limits.max_search_file_bytes}",
            *(f"--glob={glob}" for glob in _ALWAYS_EXCLUDED_GLOBS),
        ]
        if scope.kind.value == "file":
            arguments.append("--no-ignore")
        if query.glob is not None:
            arguments.append(f"--glob={query.glob}")
        arguments.append("--case-sensitive" if query.case_sensitive else "--ignore-case")
        arguments.append(query.pattern)
        return tuple(arguments)


__all__ = ["PinnedRipgrepCommandBuilder"]
