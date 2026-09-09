"""Process-group subprocess runner for adapter-owned command execution."""

from fabrica.adapters.outbound.process_group_subprocess.command import run_process_group_command
from fabrica.adapters.outbound.process_group_subprocess.contracts import (
    DEFAULT_TERMINATION_GRACE_SECONDS,
    ProcessGroupCommandResult,
    ProcessGroupCommandSettings,
)

__all__ = [
    "DEFAULT_TERMINATION_GRACE_SECONDS",
    "ProcessGroupCommandResult",
    "ProcessGroupCommandSettings",
    "run_process_group_command",
]
