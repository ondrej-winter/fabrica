"""Immutable DTOs for a workspace-scoped coding-agent session."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from fabrica.features.agent_runtime.application.dtos import SelectedSkill, SelectedSkillResource, ToolLoopRunResult

MAX_MUTATION_GATE_REASON_CHARS = 1_000
MAX_MUTATION_TOOL_NAMES = 8
MAX_TOOL_NAME_CHARS = 80


class SessionStatus(StrEnum):
    """Terminal disposition for one coding-agent session."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED_READ_ONLY = "completed_read_only"


class MutationDispositionStatus(StrEnum):
    """Safe final evidence about workspace edits attempted by the session."""

    NOT_ATTEMPTED = "not_attempted"
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class MutationGateEvidence:
    """Bounded startup evidence for whether apply-patch was exposed."""

    mutation_enabled: bool
    reason: str | None = None
    recovered_journal_digests: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.mutation_enabled and self.reason is not None:
            msg = "an enabled mutation gate cannot include a reason"
            raise ValueError(msg)
        if not self.mutation_enabled and not self.reason:
            msg = "a disabled mutation gate requires a reason"
            raise ValueError(msg)
        if self.reason is not None and len(self.reason) > MAX_MUTATION_GATE_REASON_CHARS:
            msg = "mutation gate reason exceeds the safe bound"
            raise ValueError(msg)
        object.__setattr__(self, "recovered_journal_digests", tuple(self.recovered_journal_digests))


@dataclass(frozen=True, slots=True)
class MutationDisposition:
    """Safe terminal mutation evidence derived by the composed session runtime."""

    status: MutationDispositionStatus
    tool_names: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        tool_names = tuple(self.tool_names)
        if len(tool_names) > MAX_MUTATION_TOOL_NAMES:
            msg = "mutation disposition includes too many tools"
            raise ValueError(msg)
        if any(not name or len(name) > MAX_TOOL_NAME_CHARS for name in tool_names):
            msg = "mutation disposition tool names must be bounded and non-empty"
            raise ValueError(msg)
        if self.status is MutationDispositionStatus.NOT_ATTEMPTED and tool_names:
            msg = "a non-attempted mutation disposition cannot name tools"
            raise ValueError(msg)
        if self.status is MutationDispositionStatus.APPLIED and "apply_patch" not in tool_names:
            msg = "an applied mutation disposition requires apply_patch evidence"
            raise ValueError(msg)
        object.__setattr__(self, "tool_names", tool_names)


@dataclass(frozen=True, slots=True)
class CodingAgentSessionCommand:
    """Application command for one canonical workspace-scoped coding-agent session."""

    workspace_root: Path
    prompt: str
    selected_skills: tuple[SelectedSkill, ...] = field(default_factory=tuple)
    selected_resources: tuple[SelectedSkillResource, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        workspace_root = Path(self.workspace_root)
        if not workspace_root.is_absolute():
            msg = "workspace_root must be canonical and absolute"
            raise ValueError(msg)
        if not self.prompt.strip():
            msg = "prompt must not be empty"
            raise ValueError(msg)
        object.__setattr__(self, "workspace_root", workspace_root)
        object.__setattr__(self, "selected_skills", tuple(self.selected_skills))
        object.__setattr__(self, "selected_resources", tuple(self.selected_resources))


@dataclass(frozen=True, slots=True)
class CodingAgentSessionRuntimeResult:
    """Composed runtime outcome returned through the session-owned inbound port."""

    tool_loop_result: ToolLoopRunResult
    mutation_gate: MutationGateEvidence
    mutation_disposition: MutationDisposition

    def __post_init__(self) -> None:
        if (
            not self.mutation_gate.mutation_enabled
            and self.mutation_disposition.status is MutationDispositionStatus.APPLIED
        ):
            msg = "a disabled mutation gate cannot report an applied edit"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CodingAgentSessionResult:
    """Final session result suitable for safe terminal rendering."""

    status: SessionStatus
    runtime_result: CodingAgentSessionRuntimeResult

    def __post_init__(self) -> None:
        mutation = self.runtime_result.mutation_disposition.status
        if mutation is MutationDispositionStatus.APPLIED and self.status is not SessionStatus.COMPLETED:
            msg = "an applied edit can be reported only by a completed session"
            raise ValueError(msg)
        if self.status is SessionStatus.COMPLETED_READ_ONLY and self.runtime_result.mutation_gate.mutation_enabled:
            msg = "a read-only session result requires a disabled mutation gate"
            raise ValueError(msg)
