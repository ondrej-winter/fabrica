"""Model-evidence output bridge for bootstrap-owned CLI handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.model_evidence import write_model_evidence_report

if TYPE_CHECKING:
    from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence


class ModelEvidenceResult(Protocol):
    """Result shape that can expose model evidence to the product CLI."""

    @property
    def usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        """Return usage evidence emitted by the command."""

    @property
    def cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
        """Return cost evidence emitted by the command."""


def write_requested_model_evidence(
    result: ModelEvidenceResult,
    *,
    include_usage: bool,
    include_prices: bool,
    stdout: TextIO,
) -> None:
    """Write requested usage and pricing evidence for one CLI command result."""
    write_model_evidence_report(
        usage_evidence=result.usage_evidence,
        cost_evidence=result.cost_evidence,
        stdout=stdout,
        include_usage=include_usage,
        include_prices=include_prices,
    )
