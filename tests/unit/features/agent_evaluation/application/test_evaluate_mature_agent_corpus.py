"""Tests for deterministic rule-based mature-agent corpus evaluation."""

from fabrica.features.agent_evaluation.application import EvaluateMatureAgentCorpus, EvaluationScenario
from fabrica.features.agent_evaluation.application.fixtures import mature_agent_corpus
from fabrica.features.agent_session.application.dtos import SessionEvent


def test_evaluator_reports_all_six_required_scenarios_in_stable_order() -> None:
    report = EvaluateMatureAgentCorpus(mature_agent_corpus()).execute()

    assert report.schema_version == 1
    assert report.corpus_version == 1
    assert report.passed is True
    assert [result.scenario_id for result in report.results] == [
        "approved-scoped-edit-validation",
        "denied-approval-recovery",
        "fingerprint-mismatch-replan",
        "inspect-only-success",
        "interruption-safe-boundary-resume",
        "secret-capture-exclusions",
    ]


def test_evaluator_rejects_prohibited_capture_and_missing_required_evidence() -> None:
    scenario = EvaluationScenario(
        scenario_id="invalid-capture",
        description="Regression fixture",
        events=(SessionEvent("invalid-capture", 0, "model_turn", {"credential": "secret"}),),
        required_event_kinds=frozenset({"completed"}),
    )

    result = EvaluateMatureAgentCorpus((scenario,)).execute().results[0]

    assert result.passed is False
    assert result.failures == (
        "missing required event kind: completed",
        "prohibited captured evidence: credential",
    )
