"""Tests for durable session lifecycle invariants."""

from fabrica.features.agent_session.domain import SessionState, is_legal_session_transition


def test_session_transitions_do_not_replay_terminal_or_pending_work() -> None:
    """Allow safe continuation while rejecting replay-oriented terminal paths."""
    assert is_legal_session_transition(SessionState.INTERRUPTED, SessionState.RUNNING)
    assert is_legal_session_transition(SessionState.RUNNING, SessionState.WAITING_FOR_APPROVAL)
    assert not is_legal_session_transition(SessionState.WAITING_FOR_APPROVAL, SessionState.COMPLETED)
    assert not is_legal_session_transition(SessionState.COMPLETED, SessionState.RUNNING)
