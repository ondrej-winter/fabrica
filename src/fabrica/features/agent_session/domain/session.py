"""Pure durable session lifecycle invariants."""

from enum import StrEnum


class SessionState(StrEnum):
    """Persisted lifecycle states for one agent session."""

    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE_CONTEXT = "stale_context"


_LEGAL_TRANSITIONS = {
    SessionState.RUNNING: frozenset(
        {
            SessionState.WAITING_FOR_USER,
            SessionState.WAITING_FOR_APPROVAL,
            SessionState.INTERRUPTED,
            SessionState.COMPLETED,
            SessionState.FAILED,
        }
    ),
    SessionState.WAITING_FOR_USER: frozenset({SessionState.RUNNING, SessionState.INTERRUPTED, SessionState.FAILED}),
    SessionState.WAITING_FOR_APPROVAL: frozenset({SessionState.RUNNING, SessionState.INTERRUPTED, SessionState.FAILED}),
    SessionState.INTERRUPTED: frozenset({SessionState.RUNNING, SessionState.STALE_CONTEXT}),
    SessionState.STALE_CONTEXT: frozenset({SessionState.RUNNING, SessionState.FAILED}),
    SessionState.COMPLETED: frozenset(),
    SessionState.FAILED: frozenset(),
}


def is_legal_session_transition(source: SessionState, destination: SessionState) -> bool:
    """Return whether a durable session state transition is safe."""
    return destination in _LEGAL_TRANSITIONS[source]
