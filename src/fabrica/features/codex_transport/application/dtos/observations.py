"""Safe observation DTOs for Codex transport diagnostics."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

SafeObservationValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class CodexTransportObservation:
    """Redacted diagnostic information for a Codex transport probe.

    The ``metadata`` mapping is safe-by-construction: callers must provide only
    redacted, bounded values such as status codes, error categories, counts, or
    short non-secret labels. Raw headers, tokens, cookies, request bodies, and
    response bodies do not belong in this DTO.
    """

    message: str
    metadata: Mapping[str, SafeObservationValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key, value in self.metadata.items():
            if not isinstance(key, str):
                msg = "observation metadata keys must be strings"
                raise TypeError(msg)
            if not _is_safe_observation_value(value):
                msg = f"observation metadata value for {key!r} must be a bounded scalar"
                raise TypeError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


def _is_safe_observation_value(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)
