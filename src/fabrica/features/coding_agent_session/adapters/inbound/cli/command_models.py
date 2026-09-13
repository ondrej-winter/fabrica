"""Parsed command models for coding-agent-session CLI commands."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CliSelectedResource:
    """Adapter-local reference to one explicitly selected skill resource."""

    skill_id: str
    resource_id: str


@dataclass(frozen=True, slots=True)
class CodingAgentSessionCliCompositionOptions:
    """Adapter-local options consumed by bootstrap session composition."""

    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


@dataclass(frozen=True, slots=True)
class CliCodingAgentSessionCommand:
    """Parsed CLI arguments for one workspace-scoped coding-agent session."""

    workspace_root: Path
    prompt: str
    skill_ids: tuple[str, ...] = field(default_factory=tuple)
    resources: tuple[CliSelectedResource, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_root", Path(self.workspace_root))
        object.__setattr__(self, "skill_ids", tuple(self.skill_ids))
        object.__setattr__(self, "resources", tuple(self.resources))


@dataclass(frozen=True, slots=True)
class CliSessionRecordCommand:
    """Parsed CLI arguments for a workspace-local durable session operation."""

    workspace_root: Path
    operation: str
    session_id: str | None = None
    prompt: str | None = None
    export_destination: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_root", Path(self.workspace_root))
        if self.operation in {"inspect", "delete", "resume", "export"} and not self.session_id:
            msg = "selected session operations require a session ID"
            raise ValueError(msg)
        if self.operation == "resume" and (self.prompt is None or not self.prompt.strip()):
            msg = "session resume requires a prompt"
            raise ValueError(msg)
        if self.operation == "export" and self.export_destination is None:
            msg = "session export requires a destination"
            raise ValueError(msg)
