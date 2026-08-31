"""Fail-closed workspace-contained command-current-directory resolution."""

import re
from dataclasses import dataclass
from pathlib import Path

from fabrica.features.workspace_command_execution.application.dtos import CommandErrorCode
from fabrica.features.workspace_command_execution.application.errors import CommandPlanningError

_WINDOWS_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True, slots=True)
class PosixWorkspaceCommandResolver:
    """Resolve existing command working directories under one pinned workspace root."""

    workspace_root: Path

    def resolve_cwd(self, requested_cwd: str) -> str:
        """Return a canonical workspace-relative directory or raise a safe planning error."""
        _validate_requested_cwd(requested_cwd)
        root = _resolve_root(self.workspace_root)
        candidate = root if requested_cwd == "." else root / requested_cwd
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as err:
            raise CommandPlanningError(CommandErrorCode.INVALID_CWD, "working directory does not exist") from err
        except OSError as err:
            raise CommandPlanningError(CommandErrorCode.INVALID_CWD, "working directory could not be resolved") from err
        if not resolved.is_relative_to(root):
            raise CommandPlanningError(
                CommandErrorCode.CWD_OUTSIDE_WORKSPACE, "working directory escapes the workspace"
            )
        try:
            if not resolved.is_dir():
                raise CommandPlanningError(CommandErrorCode.INVALID_CWD, "working directory is not a directory")
        except OSError as err:
            raise CommandPlanningError(
                CommandErrorCode.INVALID_CWD, "working directory could not be inspected"
            ) from err
        return str(resolved.relative_to(root)) or "."


def _validate_requested_cwd(requested_cwd: str) -> None:
    if (
        not isinstance(requested_cwd, str)
        or not requested_cwd
        or requested_cwd.startswith(("/", "\\"))
        or _WINDOWS_DRIVE_PREFIX.match(requested_cwd)
        or "\\" in requested_cwd
    ):
        raise CommandPlanningError(CommandErrorCode.INVALID_CWD, "working directory must be workspace-relative")
    if ".." in requested_cwd.split("/"):
        raise CommandPlanningError(CommandErrorCode.CWD_OUTSIDE_WORKSPACE, "working directory escapes the workspace")


def _resolve_root(workspace_root: Path) -> Path:
    try:
        root = workspace_root.resolve(strict=True)
    except FileNotFoundError as err:
        raise CommandPlanningError(CommandErrorCode.INVALID_CWD, "workspace root does not exist") from err
    except OSError as err:
        raise CommandPlanningError(CommandErrorCode.INVALID_CWD, "workspace root could not be resolved") from err
    if not root.is_dir():
        raise CommandPlanningError(CommandErrorCode.INVALID_CWD, "workspace root is not a directory")
    return root
