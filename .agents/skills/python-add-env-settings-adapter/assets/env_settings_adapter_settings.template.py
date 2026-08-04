from __future__ import annotations

from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from example_app.features.runtime_configuration.application.dtos.app_settings import (
    DEFAULT_OUTPUT_PATH,
    DEFAULT_SERVICE_URL,
)
from example_app.features.runtime_configuration.application.exceptions import ConfigurationError

BLANK_TEXT_ERROR = 'must not be blank'
ENV_PREFIX = 'EXAMPLE_APP'
REQUIRED_SECRET_ALIAS = f"{ENV_PREFIX}_REQUIRED_SECRET"
SERVICE_URL_ALIAS = f"{ENV_PREFIX}_SERVICE_URL"
OUTPUT_PATH_ALIAS = f"{ENV_PREFIX}_OUTPUT_PATH"
INVALID_CONFIGURATION_ERROR = 'Invalid runtime configuration for example app.'


class EnvSettings(BaseSettings):
    """Adapter-owned environment settings model."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        populate_by_name=True,
        extra='ignore',
    )

    required_secret: str = Field(alias=REQUIRED_SECRET_ALIAS)
    service_url: str = Field(default=DEFAULT_SERVICE_URL, alias=SERVICE_URL_ALIAS)
    output_path: Path = Field(default=DEFAULT_OUTPUT_PATH, alias=OUTPUT_PATH_ALIAS)

    @field_validator('required_secret', 'service_url', mode='before')
    @classmethod
    def validate_non_empty_text(cls, value: object) -> object:
        """Normalize and reject blank text settings."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError(BLANK_TEXT_ERROR)
            return stripped
        return value

    @field_validator('output_path', mode='before')
    @classmethod
    def validate_output_path(cls, value: object) -> object:
        """Normalize and reject blank output paths."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError(BLANK_TEXT_ERROR)
            return Path(stripped)
        return value


def load_settings_from_env() -> EnvSettings:
    """Load and validate environment-backed settings."""
    try:
        return EnvSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        raise ConfigurationError(INVALID_CONFIGURATION_ERROR) from exc
