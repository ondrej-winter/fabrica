"""Application DTOs for approved git commit creation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateGitCommitCommand:
    """Command to create a git commit from an already-approved message."""

    message: str

    def __post_init__(self) -> None:
        if not self.message.strip():
            msg = "commit message must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GitCommitResult:
    """Result returned after an approved git commit attempt succeeds."""

    short_hash: str | None = None

    def __post_init__(self) -> None:
        if self.short_hash is not None:
            short_hash = self.short_hash.strip()
            if not short_hash:
                msg = "short_hash must not be empty when provided"
                raise ValueError(msg)
            object.__setattr__(self, "short_hash", short_hash)
