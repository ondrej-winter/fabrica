"""Session-scoped safety gate for stale-context replanning."""

from dataclasses import dataclass, field
from enum import StrEnum

from fabrica.features.agent_session.application.use_cases.acknowledge_stale_context_plan import (
    AcknowledgeStaleContextPlan,
)


class ReplanSafetyState(StrEnum):
    """Required stale-context milestones before a new side effect may be proposed."""

    INSPECTION_REQUIRED = "inspection_required"
    PLAN_ACKNOWLEDGEMENT_REQUIRED = "plan_acknowledgement_required"
    SIDE_EFFECTS_PERMITTED = "side_effects_permitted"


@dataclass(slots=True)
class ReplanSafetyGate:
    """Require fresh inspection and acknowledgement without replacing action approval."""

    acknowledgements: AcknowledgeStaleContextPlan
    _inspection_completed: bool = False
    _displayed_plan_digest: str | None = None
    _state: ReplanSafetyState = field(default=ReplanSafetyState.INSPECTION_REQUIRED, init=False)

    @property
    def state(self) -> ReplanSafetyState:
        """Return the current stale-context safety state."""
        return self._state

    @property
    def side_effects_permitted(self) -> bool:
        """Return whether replan prerequisites, not ordinary approvals, are satisfied."""
        return self._state is ReplanSafetyState.SIDE_EFFECTS_PERMITTED

    def record_fresh_inspection(self) -> None:
        """Mark a successful current-workspace inspection as complete."""
        self._inspection_completed = True
        if self._state is ReplanSafetyState.INSPECTION_REQUIRED:
            self._state = ReplanSafetyState.PLAN_ACKNOWLEDGEMENT_REQUIRED

    def display_refreshed_plan(self, plan_digest: str) -> None:
        """Register one displayed plan and expire acknowledgement for a changed plan."""
        if not self._inspection_completed:
            msg = "fresh workspace inspection is required before displaying a replan"
            raise ValueError(msg)
        if self._displayed_plan_digest != plan_digest:
            self._displayed_plan_digest = plan_digest
        self._state = ReplanSafetyState.PLAN_ACKNOWLEDGEMENT_REQUIRED

    def acknowledge_displayed_plan(self, *, acknowledged: bool) -> None:
        """Persist an answer for the active displayed plan without granting action approval."""
        if self._displayed_plan_digest is None:
            msg = "a refreshed plan must be displayed before acknowledgement"
            raise ValueError(msg)
        acknowledgement = self.acknowledgements.acknowledge(
            self._displayed_plan_digest,
            acknowledged=acknowledged,
        )
        self._state = (
            ReplanSafetyState.SIDE_EFFECTS_PERMITTED
            if acknowledgement.acknowledged
            else ReplanSafetyState.PLAN_ACKNOWLEDGEMENT_REQUIRED
        )

    def side_effect_block_reason(self) -> str | None:
        """Return a stable explanation when stale-context side effects remain blocked."""
        if self.side_effects_permitted:
            return None
        if self._state is ReplanSafetyState.INSPECTION_REQUIRED:
            return "fresh workspace inspection is required before side effects"
        return "displayed refreshed-plan acknowledgement is required before side effects"
