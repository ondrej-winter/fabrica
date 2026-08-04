from example_app.features.runtime_configuration.adapters.inbound.env_settings_adapter.settings import (
    EnvSettings,
    load_settings_from_env,
)
from example_app.features.runtime_configuration.application.dtos import AppSettings


def _to_app_settings(settings: EnvSettings) -> AppSettings:
    """Convert validated environment settings to application settings."""
    return AppSettings(**settings.model_dump())


class EnvSettingsAdapter:
    """Load application settings from environment-backed configuration."""

    def load(self) -> AppSettings:
        """Return application settings loaded from the process environment."""
        return _to_app_settings(load_settings_from_env())
