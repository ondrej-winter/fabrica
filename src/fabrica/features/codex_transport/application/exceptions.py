"""Application exceptions for Codex transport orchestration."""


class CodexCredentialStoreError(Exception):
    """Base class for safe credential-loading failures."""


class CodexCredentialUnavailableError(CodexCredentialStoreError):
    """Credentials could not be loaded, parsed, or validated."""


class CodexCredentialAuthenticationError(CodexCredentialStoreError):
    """Credentials are unavailable for authentication semantics."""
