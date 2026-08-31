"""Alembic environment backed by Cadmus settings and application metadata."""

from logging.config import fileConfig

import cadmus.infrastructure.identity
import cadmus.infrastructure.reference_lexicon
import cadmus.infrastructure.reference_links
import cadmus.infrastructure.sources  # noqa: F401
from alembic import context
from cadmus.config import Settings
from cadmus.infrastructure.database import metadata
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings()
config.set_main_option(
    "sqlalchemy.url",
    settings.sqlalchemy_database_url()
    .render_as_string(hide_password=False)
    .replace("%", "%%"),
)
target_metadata = metadata


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a fail-fast PostgreSQL connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
