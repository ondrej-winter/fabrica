"""Contracts and injected dependencies for coding-agent-session CLI commands."""

from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True, slots=True)
class CodingAgentSessionCliStreams:
    """Normalized CLI input/output streams for one coding-agent session."""

    stdout: TextIO
    stderr: TextIO
