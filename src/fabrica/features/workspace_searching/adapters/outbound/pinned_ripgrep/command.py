"""Build fixed, sandboxed ripgrep commands from canonical search requests."""

from dataclasses import dataclass
from pathlib import Path

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import (
    PinnedRipgrepExecutable,
    verified_pinned_ripgrep_executable,
)
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import SearchSandbox, SearchScope
from fabrica.features.workspace_searching.application.dtos import SearchLimits, SearchQuery

_ALWAYS_EXCLUDED_GLOBS = ("!.git/**", "!node_modules/**")


@dataclass(frozen=True, slots=True)
class PinnedRipgrepCommandBuilder:
    """Construct one contained pinned-ripgrep command without shell interpretation."""

    workspace_root: Path

    def command_for(self, query: SearchQuery, scope: SearchScope, limits: SearchLimits) -> tuple[str, ...]:
        """Return fixed backend arguments enclosed by the workspace sandbox command."""
        executable = verified_pinned_ripgrep_executable()
        backend_argv = self._backend_argv(executable, query, scope, limits)
        return SearchSandbox(self.workspace_root).command_for(backend_argv, scope)

    def _backend_argv(
        self,
        executable: PinnedRipgrepExecutable,
        query: SearchQuery,
        scope: SearchScope,
        limits: SearchLimits,
    ) -> tuple[str, ...]:
        arguments = [
            str(executable.path),
            "--json",
            "--hidden",
            "--no-follow",
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
