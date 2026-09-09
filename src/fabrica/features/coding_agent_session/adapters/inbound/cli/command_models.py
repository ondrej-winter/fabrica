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
