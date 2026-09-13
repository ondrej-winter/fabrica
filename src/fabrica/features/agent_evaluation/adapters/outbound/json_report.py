"""Deterministic JSON report adapter for offline evaluation results."""

import json
from dataclasses import dataclass
from pathlib import Path

from fabrica.features.agent_evaluation.application.dtos import EvaluationReport


@dataclass(frozen=True, slots=True)
class JsonEvaluationReportWriter:
    """Write deterministic evaluation reports as local JSON files."""

    def write(self, report: EvaluationReport, destination: Path) -> Path:
        """Write one deterministic report file and return its resolved path."""
        path = destination.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_report_payload(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path


def _report_payload(report: EvaluationReport) -> dict[str, object]:
    return {
        "corpus_version": report.corpus_version,
        "passed": report.passed,
        "results": [
            {
                "assertions": list(result.assertions),
                "failures": list(result.failures),
                "passed": result.passed,
                "scenario_id": result.scenario_id,
            }
            for result in report.results
        ],
        "schema_version": report.schema_version,
    }
