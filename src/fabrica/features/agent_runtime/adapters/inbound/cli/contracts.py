"""Contracts and injected dependencies for agent-runtime CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from fabrica.features.agent_runtime.application.dtos import (
        LocalAgentRunResult,
    )


class EvidenceWriter(Protocol):
    """Writer for requested model evidence after command output."""

    def __call__(
        self,
        result: LocalAgentRunResult,
        *,
        include_usage: bool,
        include_prices: bool,
        stdout: TextIO,
    ) -> None:
        """Write model evidence selected by global CLI options."""


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliOptions:
    """Product CLI option values consumed by agent-runtime commands."""

    print_usage: bool = False
    print_prices: bool = False


@dataclass(frozen=True, slots=True)
class AgentRuntimeCliStreams:
    """Normalized CLI input/output streams for agent-runtime commands."""

    stdout: TextIO
    stderr: TextIO
