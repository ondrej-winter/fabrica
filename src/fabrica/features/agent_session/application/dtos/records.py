"""Immutable, provider-neutral durable-session boundary types."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from fabrica.features.agent_session.domain import SessionState

SESSION_RECORD_SCHEMA_VERSION = 1
MAX_RESUME_EVENTS = 200

SafeSessionValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class SessionEvent:
    """Normalized completed evidence recorded before runtime continuation."""

    session_id: str
    sequence: int
    kind: str
    payload: Mapping[str, SafeSessionValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the portable, structured event boundary."""
        if not self.session_id or self.sequence < 0 or not self.kind:
            msg = "session events require a session id, non-negative sequence, and kind"
            raise ValueError(msg)
        payload = dict(self.payload)
        if any(
            not isinstance(key, str) or not isinstance(value, (str, int, float, bool, type(None)))
            for key, value in payload.items()
        ):
            msg = "session event payload values must be scalar application evidence"
            raise TypeError(msg)
        object.__setattr__(self, "payload", MappingProxyType(payload))


@dataclass(frozen=True, slots=True)
class WorkspaceFingerprint:
    """A deterministic workspace snapshot or fail-closed unavailable disposition."""

    digest: str | None
    manifest: tuple[str, ...] = field(default_factory=tuple)
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        """Keep available and unavailable fingerprint states unambiguous."""
        if (self.digest is None) == (self.unavailable_reason is None):
            msg = "a fingerprint is either available or unavailable"
            raise ValueError(msg)
        if self.digest is not None and not self.digest.startswith("sha256:"):
            msg = "fingerprint digest must be SHA-256"
            raise ValueError(msg)
        object.__setattr__(self, "manifest", tuple(self.manifest))

    @property
    def available(self) -> bool:
        """Return whether resume comparison may use this fingerprint."""
        return self.digest is not None


@dataclass(frozen=True, slots=True)
class SessionCheckpoint:
    """Completed durable context only; never suspended executable work."""

    session_id: str
    sequence: int
    state: SessionState
    workspace_fingerprint: WorkspaceFingerprint
    completed_summary: str

    def __post_init__(self) -> None:
        """Reject a checkpoint that would preserve a pending interaction."""
        if not self.session_id or self.sequence < 0 or not self.completed_summary:
            msg = "checkpoints require completed session evidence"
            raise ValueError(msg)
        if self.state in {SessionState.WAITING_FOR_APPROVAL, SessionState.WAITING_FOR_USER}:
            msg = "a checkpoint cannot preserve pending interaction or approval work"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ResumeContext:
    """Provider-neutral context used to start one fresh continuation turn."""

    checkpoint: SessionCheckpoint
    later_events: tuple[SessionEvent, ...] = field(default_factory=tuple)
    continuation_instruction: str = (
        "Treat this history as context only. Inspect the current workspace before proposing work; "
        "do not replay historical actions."
    )

    def __post_init__(self) -> None:
        """Require bounded ordered evidence following the completed checkpoint."""
        events = tuple(self.later_events)
        if len(events) > MAX_RESUME_EVENTS:
            msg = "resume context exceeds the later-event bound"
            raise ValueError(msg)
        if any(
            event.session_id != self.checkpoint.session_id or event.sequence <= self.checkpoint.sequence
            for event in events
        ):
            msg = "resume context later events must follow its checkpoint"
            raise ValueError(msg)
        if tuple(sorted(event.sequence for event in events)) != tuple(event.sequence for event in events):
            msg = "resume context later events must be ordered"
            raise ValueError(msg)
        object.__setattr__(self, "later_events", events)


@dataclass(frozen=True, slots=True)
class StaleContextAcknowledgement:
    """A refreshed-plan acknowledgement, distinct from answers and approvals."""

    plan_digest: str
    acknowledged: bool

    def __post_init__(self) -> None:
        """Bind acknowledgement to one current refreshed plan digest."""
        if not self.plan_digest.startswith("sha256:"):
            msg = "stale-context acknowledgement requires a plan digest"
            raise ValueError(msg)
