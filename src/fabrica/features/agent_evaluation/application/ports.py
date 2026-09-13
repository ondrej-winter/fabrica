"""Application-owned outbound ports for deterministic mature-agent evaluation."""

from pathlib import Path
from typing import Protocol

from fabrica.features.agent_evaluation.application.dtos import EvaluationReport


class EvaluationReportWriter(Protocol):
    """Persist one deterministic evaluation report at a caller-selected path."""

    def write(self, report: EvaluationReport, destination: Path) -> Path:
        """Write the report and return its resolved destination."""
