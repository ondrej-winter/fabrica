"""Workspace editing application use cases."""

from fabrica.features.workspace_editing.application.use_cases.match_hunks import MatchHunks, MatchHunksResult
from fabrica.features.workspace_editing.application.use_cases.parse_patch import ParsePatch, ParsePatchResult
from fabrica.features.workspace_editing.application.use_cases.plan_patch import (
    PatchPlanningSnapshot,
    PlanPatch,
    PlanPatchResult,
)

__all__ = [
    "MatchHunks",
    "MatchHunksResult",
    "ParsePatch",
    "ParsePatchResult",
    "PatchPlanningSnapshot",
    "PlanPatch",
    "PlanPatchResult",
]
