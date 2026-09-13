"""Provider-neutral DTOs for deterministic mature-agent evaluation."""

from dataclasses import dataclass

from fabrica.features.agent_session.application.dtos import SessionEvent

EVALUATION_REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class EvaluationScenario:
    """One normalized offline evidence fixture and its required outcomes."""

    scenario_id: str
    description: str
    events: tuple[SessionEvent, ...]
    required_event_kinds: frozenset[str]
    forbidden_payload_fragments: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Require stable IDs and evidence for every corpus scenario."""
        if not self.scenario_id or not self.description or not self.events:
            msg = "evaluation scenarios require an id, description, and normalized evidence"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EvaluationScenarioResult:
    """Stable result fields for one deterministic evaluation scenario."""

    scenario_id: str
    passed: bool
    assertions: tuple[str, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Versioned reporting-only result for the complete offline corpus."""

    schema_version: int
    corpus_version: int
    results: tuple[EvaluationScenarioResult, ...]

    @property
    def passed(self) -> bool:
        """Return whether every fixed corpus scenario passed."""
        return all(result.passed for result in self.results)
