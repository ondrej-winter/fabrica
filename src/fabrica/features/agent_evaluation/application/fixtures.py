"""Canonical Version 1 offline mature-agent evaluation fixture corpus."""

from fabrica.features.agent_evaluation.application.dtos import EvaluationScenario
from fabrica.features.agent_session.application.dtos import SessionEvent


def mature_agent_corpus() -> tuple[EvaluationScenario, ...]:
    """Return the fixed six-scenario corpus from Mature Agent MVP requirement R7."""
    return (
        _scenario(
            "approved-scoped-edit-validation",
            "Approved scoped edit plus validation",
            ("apply_patch", "run_commands"),
        ),
        _scenario(
            "denied-approval-recovery",
            "Denied approval recovery",
            ("approval_denied", "model_turn", "completed"),
        ),
        _scenario(
            "fingerprint-mismatch-replan",
            "Fingerprint mismatch stale-context replan",
            ("stale_context", "workspace_inspected", "stale_context_plan_acknowledged", "completed"),
        ),
        _scenario(
            "inspect-only-success",
            "Inspect-only successful session",
            ("model_turn", "read_files", "completed"),
        ),
        _scenario(
            "interruption-safe-boundary-resume",
            "Interruption and safe-boundary resume",
            ("interrupted", "resume_context_created", "model_turn", "completed"),
        ),
        _scenario(
            "secret-capture-exclusions",
            "Secret-capture exclusions",
            ("model_turn", "tool_completed", "completed"),
        ),
    )


def _scenario(scenario_id: str, description: str, required_kinds: tuple[str, ...]) -> EvaluationScenario:
    events = tuple(
        SessionEvent(
            session_id=scenario_id,
            sequence=index,
            kind=kind,
            payload={"evidence": "normalized"},
        )
        for index, kind in enumerate(required_kinds)
    )
    return EvaluationScenario(
        scenario_id=scenario_id,
        description=description,
        events=events,
        required_event_kinds=frozenset(required_kinds),
    )
