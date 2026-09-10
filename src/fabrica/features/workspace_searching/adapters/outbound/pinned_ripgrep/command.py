"""Build fixed direct native ripgrep commands from canonical search requests."""

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.manifest import (
    PinnedRipgrepUnavailableError,
    verified_pinned_ripgrep_executable,
)
from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem import SearchScope
from fabrica.features.workspace_searching.application.dtos import SearchLimits, SearchQuery

_ALWAYS_EXCLUDED_GLOBS = ("!.git/**", "!node_modules/**")


def build_pinned_ripgrep_command(query: SearchQuery, scope: SearchScope, limits: SearchLimits) -> tuple[str, ...]:
    """Return fixed verified-ripgrep arguments with the validated canonical scope."""
    executable = verified_pinned_ripgrep_executable()
    if executable.platform_key not in {"linux-x86_64", "darwin-arm64"}:
        msg = "pinned ripgrep backend is unavailable for this platform"
        raise PinnedRipgrepUnavailableError(msg)
    arguments = [
        str(executable.path),
        "--json",
        "--no-config",
        "--hidden",
        "--no-follow",
        "--no-ignore-parent",
        f"--max-filesize={limits.max_search_file_bytes}",
    ]
    if scope.kind.value == "file":
        arguments.append("--no-ignore")
    if query.glob is not None:
        arguments.append(f"--glob={query.glob}")
    arguments.extend(f"--glob={glob}" for glob in _ALWAYS_EXCLUDED_GLOBS)
    arguments.append("--case-sensitive" if query.case_sensitive else "--ignore-case")
    arguments.extend((query.pattern, str(scope.canonical_path)))
    return tuple(arguments)


__all__ = ["build_pinned_ripgrep_command"]
