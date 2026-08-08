"""Application-safe exceptions for Codex transport credential loading."""

__all__ = [
    "CodexCredentialAuthenticationError",
    "CodexCredentialStoreError",
    "CodexCredentialUnavailableError",
]


class CodexCredentialStoreError(Exception):
    """Base class for safe credential-loading failures."""


class CodexCredentialUnavailableError(CodexCredentialStoreError):
    """Credentials could not be loaded, parsed, or validated."""


class CodexCredentialAuthenticationError(CodexCredentialStoreError):
    """Credentials are unavailable for authentication semantics."""
