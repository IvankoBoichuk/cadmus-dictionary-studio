import pytest
from cadmus.config import Environment, Settings
from pydantic import SecretStr, ValidationError


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings()

    assert settings.name == "cadmus-api"
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.version == "0.1.0"
    assert settings.database_name == "cadmus"
    assert settings.database_host == "localhost"
    assert settings.database_port == 5432
    assert settings.sqlalchemy_database_url().drivername == "postgresql+psycopg"


def test_settings_are_read_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CADMUS_NAME", "configured-api")
    monkeypatch.setenv("CADMUS_ENVIRONMENT", "staging")
    monkeypatch.setenv("CADMUS_VERSION", "2.4.6")
    monkeypatch.setenv("CADMUS_DATABASE_NAME", "cadmus_dev")
    monkeypatch.setenv("CADMUS_DATABASE_USER", "developer")
    monkeypatch.setenv("CADMUS_DATABASE_PASSWORD", "not-logged")
    monkeypatch.setenv("CADMUS_DATABASE_HOST", "database.internal")
    monkeypatch.setenv("CADMUS_DATABASE_PORT", "5433")

    settings = Settings()

    assert settings.name == "configured-api"
    assert settings.environment is Environment.STAGING
    assert settings.version == "2.4.6"
    database_url = settings.sqlalchemy_database_url()
    assert database_url.database == "cadmus_dev"
    assert database_url.username == "developer"
    assert database_url.password == "not-logged"
    assert database_url.host == "database.internal"
    assert database_url.port == 5433


def test_full_database_url_overrides_individual_connection_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CADMUS_DATABASE_URL",
        "postgresql+psycopg://override:secret@override-db:5544/override_name",
    )
    monkeypatch.setenv("CADMUS_DATABASE_HOST", "ignored-host")

    settings = Settings()
    database_url = settings.sqlalchemy_database_url()

    assert database_url.database == "override_name"
    assert database_url.username == "override"
    assert database_url.password == "secret"
    assert database_url.host == "override-db"
    assert database_url.port == 5544


def test_settings_representations_do_not_expose_database_credentials() -> None:
    settings = Settings(database_password=SecretStr("highly-sensitive"))

    assert "highly-sensitive" not in repr(settings)
    assert "highly-sensitive" not in str(settings.sqlalchemy_database_url())


def test_database_url_encodes_reserved_password_characters() -> None:
    settings = Settings(database_password=SecretStr("p@ss:/%word"))

    database_url = settings.sqlalchemy_database_url()

    assert database_url.password == "p@ss:/%word"
    assert "p%40ss%3A%2F%25word" in database_url.render_as_string(hide_password=False)


@pytest.mark.parametrize("field", ["name", "version"])
def test_settings_reject_blank_metadata(
    field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"CADMUS_{field.upper()}", "   ")

    with pytest.raises(ValidationError):
        Settings()
