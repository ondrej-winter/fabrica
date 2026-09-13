"""Domain rules for durable agent sessions."""

from fabrica.features.agent_session.domain.session import SessionState, is_legal_session_transition

__all__ = ["SessionState", "is_legal_session_transition"]
