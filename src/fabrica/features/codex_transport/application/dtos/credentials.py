"""Credential DTOs for the Codex transport application boundary."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CodexCredentials:
    """In-memory Codex credentials required by the transport boundary.

    Values are secret-bearing and must not be logged, persisted, or exposed in
    diagnostics. Adapters are responsible for redacting these values before
    constructing observations or exception messages.
    """

    access_token: str
    account_id: str
