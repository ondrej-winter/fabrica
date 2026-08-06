"""Adapter-owned HTTP response DTOs for Codex backend mapping."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class CodexBackendResponse:
    """Adapter-owned HTTP response shape for deterministic completion mapping."""

    status_code: int
    headers: Mapping[str, str]
    json_body: object

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True, slots=True)
class CodexUsageResponse:
    """Adapter-owned HTTP response shape for deterministic usage mapping."""

    status_code: int
    headers: Mapping[str, str]
    json_body: object

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))
