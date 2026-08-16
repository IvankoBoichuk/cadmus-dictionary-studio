"""Real PostgreSQL contract tests for connection and Alembic migrations."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

pytestmark = pytest.mark.integration

EXPECTED_REVISION = "bh29_0007"


def _test_database_url() -> str:
    database_url = os.environ["CADMUS_TEST_DATABASE_URL"]
    parsed_url = make_url(database_url)
    if parsed_url.database is None or not parsed_url.database.endswith("_test"):
        raise RuntimeError("integration tests require a *_test database")
    return database_url


def _alembic_config(database_url: str) -> Config:
    os.environ["CADMUS_DATABASE_URL"] = database_url
    return Config("alembic.ini")


def _current_revision(database_url: str) -> str | None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def test_postgresql_connection_and_reversible_idempotent_migration() -> None:
    database_url = _test_database_url()
    alembic_config = _alembic_config(database_url)
    engine = create_engine(database_url)

    command.downgrade(alembic_config, "base")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
        assert "cadmus" not in inspect(connection).get_schema_names()

    command.upgrade(alembic_config, "head")
    assert _current_revision(database_url) == EXPECTED_REVISION

    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "cadmus" in inspector.get_schema_names()
        assert sorted(inspector.get_table_names(schema="cadmus")) == [
            "authenticated_sessions",
            "dictionaries",
            "dictionary_abbreviation_variants",
            "dictionary_abbreviations",
            "dictionary_contributors",
            "dictionary_events",
            "dictionary_languages",
            "dictionary_pages",
            "dictionary_source_files",
            "email_verification_tokens",
            "password_reset_tokens",
            "users",
        ]
        assert inspector.get_table_names(schema="public") == ["alembic_version"]

    command.upgrade(alembic_config, "head")
    assert _current_revision(database_url) == EXPECTED_REVISION

    command.downgrade(alembic_config, "base")
    with engine.connect() as connection:
        assert "cadmus" not in inspect(connection).get_schema_names()

    command.upgrade(alembic_config, "head")
    assert _current_revision(database_url) == EXPECTED_REVISION
    engine.dispose()


def test_migration_connection_failure_is_not_hidden() -> None:
    database_url = make_url(_test_database_url()).set(password="invalid-password")
    alembic_config = _alembic_config(database_url.render_as_string(hide_password=False))

    with pytest.raises(OperationalError):
        command.current(alembic_config)
