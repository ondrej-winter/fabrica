"""Digest-bound acknowledgement for a displayed stale-context replan."""

from dataclasses import dataclass, field

from fabrica.features.agent_session.application.dtos import SessionEvent, StaleContextAcknowledgement
from fabrica.features.agent_session.application.ports import SessionRecordStore


@dataclass(slots=True)
class AcknowledgeStaleContextPlan:
    """Track one current replan acknowledgement without granting side-effect authority."""

    store: SessionRecordStore
    session_id: str
    _acknowledged_plan_digests: set[str] = field(default_factory=set)

    def acknowledge(self, plan_digest: str, *, acknowledged: bool) -> StaleContextAcknowledgement:
        """Record an explicit answer for one displayed plan digest only."""
        acknowledgement = StaleContextAcknowledgement(plan_digest=plan_digest, acknowledged=acknowledged)
        sequence = _next_sequence(self.store.load_events(self.session_id))
        self.store.append_event(
            SessionEvent(
                session_id=self.session_id,
                sequence=sequence,
                kind="stale_context_plan_acknowledged",
                payload={"plan_digest": plan_digest, "acknowledged": acknowledged},
            )
        )
        if acknowledged:
            self._acknowledged_plan_digests.add(plan_digest)
        else:
            self._acknowledged_plan_digests.discard(plan_digest)
        return acknowledgement

    def is_acknowledged(self, plan_digest: str) -> bool:
        """Return whether this exact current plan digest was acknowledged."""
        return plan_digest in self._acknowledged_plan_digests


def _next_sequence(events: tuple[SessionEvent, ...]) -> int:
    return events[-1].sequence + 1 if events else 0
