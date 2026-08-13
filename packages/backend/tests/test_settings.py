import pytest
from cadmus.config import Environment, Settings
from pydantic import ValidationError


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings()

    assert settings.name == "cadmus-api"
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.version == "0.1.0"


def test_settings_are_read_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CADMUS_NAME", "configured-api")
    monkeypatch.setenv("CADMUS_ENVIRONMENT", "staging")
    monkeypatch.setenv("CADMUS_VERSION", "2.4.6")

    settings = Settings()

    assert settings.name == "configured-api"
    assert settings.environment is Environment.STAGING
    assert settings.version == "2.4.6"


@pytest.mark.parametrize("field", ["name", "version"])
def test_settings_reject_blank_metadata(
    field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"CADMUS_{field.upper()}", "   ")

    with pytest.raises(ValidationError):
        Settings()
