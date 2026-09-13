"""Durable normalized lifecycle capture for one tool-aware agent session."""

from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    ToolAwareModelResponse,
    ToolCallResult,
    ToolLoopRunResult,
)
from fabrica.features.agent_session.application.dtos import SessionCheckpoint, SessionEvent
from fabrica.features.agent_session.application.ports import SessionRecordStore, WorkspaceFingerprintBuilder
from fabrica.features.agent_session.domain import SessionState

_SENSITIVITY_WARNING = "Session records are sensitive local artifacts."


class SessionRecordingError(RuntimeError):
    """Raised when required durable session evidence cannot be persisted."""


@dataclass(slots=True)
class RecordSessionLifecycle:
    """Synchronously persist normalized evidence for one session lifecycle."""

    session_id: str
    store: SessionRecordStore
    fingerprint_builder: WorkspaceFingerprintBuilder
    _sequence: int = 0
    _started: bool = False

    def start(self) -> None:
        """Persist the warning and initial running checkpoint before model activity."""
        if self._started:
            return
        self._append("sensitivity_warning", {"message": _SENSITIVITY_WARNING})
        self._append("state_changed", {"state": SessionState.RUNNING.value})
        self._save_checkpoint(SessionState.RUNNING, "Session started.")
        self._started = True

    def record_model_response(self, response: ToolAwareModelResponse) -> None:
        """Persist provider-neutral completed model-turn metadata."""
        self._require_started()
        self._append(
            "model_turn_completed",
            {"has_output": response.output_text is not None, "tool_call_count": len(response.tool_calls)},
        )

    def record_tool_result(self, result: ToolCallResult) -> None:
        """Persist one completed tool outcome without arguments or result content."""
        self._require_started()
        self._append(
            "tool_call_completed",
            {"status": result.status.value, "tool_name": result.tool_name},
        )

    def finish(self, result: ToolLoopRunResult) -> None:
        """Persist the terminal disposition and a resumable completed checkpoint."""
        self._require_started()
        state = SessionState.COMPLETED if result.succeeded else SessionState.FAILED
        self._append("run_completed", {"status": result.status.value})
        self._append("state_changed", {"state": state.value})
        self._save_checkpoint(state, f"Tool loop finished with status: {result.status.value}.")

    def _append(self, kind: str, payload: Mapping[str, SafeRuntimeMetadataValue]) -> None:
        try:
            self.store.append_event(SessionEvent(self.session_id, self._sequence, kind, payload))
        except OSError as err:
            msg = "durable session event recording failed"
            raise SessionRecordingError(msg) from err
        self._sequence += 1

    def _save_checkpoint(self, state: SessionState, summary: str) -> None:
        try:
            self.store.save_checkpoint(
                SessionCheckpoint(
                    session_id=self.session_id,
                    sequence=self._sequence - 1,
                    state=state,
                    workspace_fingerprint=self.fingerprint_builder.build(),
                    completed_summary=summary,
                )
            )
        except OSError as err:
            msg = "durable session checkpoint recording failed"
            raise SessionRecordingError(msg) from err

    def _require_started(self) -> None:
        if not self._started:
            msg = "session recording must start before runtime activity"
            raise SessionRecordingError(msg)
