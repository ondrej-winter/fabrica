from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from example_app.features.runtime_configuration.adapters.inbound.env_settings_adapter import (
    EnvSettingsAdapter,
)
from example_app.features.runtime_configuration.adapters.inbound.env_settings_adapter.settings import (
    OUTPUT_PATH_ALIAS,
    REQUIRED_SECRET_ALIAS,
    SERVICE_URL_ALIAS,
)
from example_app.features.runtime_configuration.application.dtos.app_settings import (
    DEFAULT_OUTPUT_PATH,
    DEFAULT_SERVICE_URL,
)
from example_app.features.runtime_configuration.application.exceptions import ConfigurationError

if TYPE_CHECKING:
    from pathlib import Path

REQUIRED_SECRET_VALUE = 'local-secret-value'


@pytest.fixture(autouse=True)
def isolate_env_file_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prevent developer-local `.env` files from affecting settings tests."""
    monkeypatch.chdir(tmp_path)


def test_missing_required_secret_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(REQUIRED_SECRET_ALIAS, raising=False)
    monkeypatch.delenv(OUTPUT_PATH_ALIAS, raising=False)

    with pytest.raises(ConfigurationError, match='Invalid runtime configuration'):
        EnvSettingsAdapter().load()


@pytest.mark.parametrize('raw_value', ['', '   '])
def test_blank_required_secret_raises_configuration_error(monkeypatch: pytest.MonkeyPatch, raw_value: str) -> None:
    monkeypatch.setenv(REQUIRED_SECRET_ALIAS, raw_value)

    with pytest.raises(ConfigurationError, match='Invalid runtime configuration'):
        EnvSettingsAdapter().load()


def test_valid_required_secret_loads_app_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REQUIRED_SECRET_ALIAS, f"  {REQUIRED_SECRET_VALUE}  ")
    monkeypatch.delenv(SERVICE_URL_ALIAS, raising=False)
    monkeypatch.delenv(OUTPUT_PATH_ALIAS, raising=False)

    settings = EnvSettingsAdapter().load()

    assert settings.required_secret == REQUIRED_SECRET_VALUE
    assert settings.service_url == DEFAULT_SERVICE_URL
    assert settings.output_path == DEFAULT_OUTPUT_PATH


def test_service_url_override_loads_app_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REQUIRED_SECRET_ALIAS, REQUIRED_SECRET_VALUE)
    monkeypatch.setenv(SERVICE_URL_ALIAS, '  https://service.example.test  ')

    settings = EnvSettingsAdapter().load()

    assert settings.service_url == 'https://service.example.test'


def test_blank_service_url_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REQUIRED_SECRET_ALIAS, REQUIRED_SECRET_VALUE)
    monkeypatch.setenv(SERVICE_URL_ALIAS, '  ')

    with pytest.raises(ConfigurationError, match='Invalid runtime configuration'):
        EnvSettingsAdapter().load()


def test_output_path_override_loads_app_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / 'output.sqlite3'
    monkeypatch.setenv(REQUIRED_SECRET_ALIAS, REQUIRED_SECRET_VALUE)
    monkeypatch.setenv(OUTPUT_PATH_ALIAS, f"  {output_path}  ")

    settings = EnvSettingsAdapter().load()

    assert settings.output_path == output_path


def test_blank_output_path_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REQUIRED_SECRET_ALIAS, REQUIRED_SECRET_VALUE)
    monkeypatch.setenv(OUTPUT_PATH_ALIAS, '  ')

    with pytest.raises(ConfigurationError, match='Invalid runtime configuration'):
        EnvSettingsAdapter().load()


def test_unrelated_environment_variables_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REQUIRED_SECRET_ALIAS, REQUIRED_SECRET_VALUE)
    monkeypatch.setenv('UNRELATED_SETTING', 'ignored')

    settings = EnvSettingsAdapter().load()

    assert settings.required_secret == REQUIRED_SECRET_VALUE
