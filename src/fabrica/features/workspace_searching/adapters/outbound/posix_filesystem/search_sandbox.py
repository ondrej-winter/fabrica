"""Fail-closed subprocess containment command construction for workspace search."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fabrica.features.workspace_searching.adapters.outbound.posix_filesystem.path_resolution import SearchScope

_LINUX_WORKSPACE_MOUNT = Path("/workspace")


@dataclass(slots=True)
class SearchSandboxUnavailableError(Exception):
    """Raised before launch when the host cannot provide search containment."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class SearchSandbox:
    """Build a sandboxed command that confines a pinned backend to one workspace.

    The caller must pass only a verified backend executable and fixed backend
    arguments. This class deliberately offers command construction rather than an
    unrestricted process API, so T3 owns supervised process lifetime and parsing.
    """

    workspace_root: Path

    def command_for(self, backend_argv: tuple[str, ...], scope: SearchScope) -> tuple[str, ...]:
        """Return a sandboxed backend command with the verified scope appended."""
        if not backend_argv:
            msg = "backend command must not be empty"
            raise ValueError(msg)
        root = self.workspace_root.resolve(strict=True)
        if not scope.canonical_path.is_relative_to(root):
            msg = "search scope must remain inside the configured workspace"
            raise SearchSandboxUnavailableError(msg)
        if sys.platform == "linux":
            return self._linux_command(backend_argv, root, scope)
        msg = "workspace search subprocess containment is unsupported on this platform"
        raise SearchSandboxUnavailableError(msg)

    def _linux_command(self, backend_argv: tuple[str, ...], root: Path, scope: SearchScope) -> tuple[str, ...]:
        bubblewrap = shutil.which("bwrap")
        if bubblewrap is None:
            msg = "Linux workspace search containment requires bubblewrap"
            raise SearchSandboxUnavailableError(msg)
        scope_path = _LINUX_WORKSPACE_MOUNT / scope.workspace_relative_path
        rewritten_argv = (*backend_argv, str(scope_path))
        return (
            bubblewrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--share-net",
            "--ro-bind",
            str(root),
            str(_LINUX_WORKSPACE_MOUNT),
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--chdir",
            str(_LINUX_WORKSPACE_MOUNT),
            "--",
            *rewritten_argv,
        )


__all__ = ["SearchSandbox", "SearchSandboxUnavailableError"]
