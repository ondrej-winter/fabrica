class ApplicationError(Exception):
    """Base class for application-layer errors."""


class ConfigurationError(ApplicationError):
    """Raised when runtime configuration is missing or invalid."""
