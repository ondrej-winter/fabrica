"""Rule-based evaluator for normalized mature-agent session evidence."""

import json
from dataclasses import dataclass

from fabrica.features.agent_evaluation.application.dtos import (
    EVALUATION_REPORT_SCHEMA_VERSION,
    EvaluationReport,
    EvaluationScenario,
    EvaluationScenarioResult,
)

MATURE_AGENT_CORPUS_VERSION = 1
_PROHIBITED_CAPTURE_FRAGMENTS = frozenset(
    {
        "auth_header",
        "credential",
        "process_environment",
        "raw_provider_payload",
        "terminal_keystroke",
    }
)


@dataclass(frozen=True, slots=True)
class EvaluateMatureAgentCorpus:
    """Evaluate fixed normalized fixtures without models, credentials, or network I/O."""

    scenarios: tuple[EvaluationScenario, ...]

    def execute(self) -> EvaluationReport:
        """Evaluate every scenario in deterministic scenario-ID order."""
        ordered_scenarios = sorted(self.scenarios, key=lambda item: item.scenario_id)
        return EvaluationReport(
            schema_version=EVALUATION_REPORT_SCHEMA_VERSION,
            corpus_version=MATURE_AGENT_CORPUS_VERSION,
            results=tuple(self._evaluate(scenario) for scenario in ordered_scenarios),
        )

    def _evaluate(self, scenario: EvaluationScenario) -> EvaluationScenarioResult:
        kinds = {event.kind for event in scenario.events}
        failures = [f"missing required event kind: {kind}" for kind in sorted(scenario.required_event_kinds - kinds)]
        serialized_evidence = _serialize_evidence(scenario)
        forbidden_fragments = _PROHIBITED_CAPTURE_FRAGMENTS | scenario.forbidden_payload_fragments
        failures.extend(
            f"prohibited captured evidence: {fragment}"
            for fragment in sorted(forbidden_fragments)
            if fragment in serialized_evidence
        )
        assertions = (
            "normalized session evidence is present",
            "required transcript, tool, and state events are present",
            "prohibited host and provider capture fragments are absent",
        )
        return EvaluationScenarioResult(
            scenario_id=scenario.scenario_id,
            passed=not failures,
            assertions=assertions,
            failures=tuple(failures),
        )


def _serialize_evidence(scenario: EvaluationScenario) -> str:
    return json.dumps(
        [{"kind": event.kind, "payload": dict(event.payload), "sequence": event.sequence} for event in scenario.events],
        sort_keys=True,
        separators=(",", ":"),
    ).lower()
