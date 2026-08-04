from example_app.features.runtime_configuration.application.dtos import AppSettings

REQUIRED_SECRET_VALUE = 'local-secret-value'


def test_app_settings_preserves_required_secret() -> None:
    settings = AppSettings(required_secret=REQUIRED_SECRET_VALUE)

    assert settings.required_secret == REQUIRED_SECRET_VALUE
