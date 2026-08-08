"""Shared Codex usage evidence mapper DTOs."""

from dataclasses import dataclass, field

from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence

CODEX_PROVIDER = "codex"


@dataclass(frozen=True, slots=True)
class CodexGenericEvidence:
    """Generic usage and cost evidence derived from Codex-safe facts."""

    usage_evidence: tuple[ModelUsageEvidence, ...] = field(default_factory=tuple)
    cost_evidence: tuple[ModelCostEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "usage_evidence", tuple(self.usage_evidence))
        object.__setattr__(self, "cost_evidence", tuple(self.cost_evidence))


__all__ = ["CODEX_PROVIDER", "CodexGenericEvidence"]
