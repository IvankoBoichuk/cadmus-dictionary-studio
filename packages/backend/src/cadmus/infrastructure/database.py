"""SQLAlchemy infrastructure shared by API and migration entrypoints."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine

from cadmus.config import Settings

SCHEMA_NAME = "cadmus"

NAMING_CONVENTION: Mapping[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(schema=SCHEMA_NAME, naming_convention=NAMING_CONVENTION)


def create_database_engine(
    settings: Settings,
    **engine_options: Any,
) -> Engine:
    """Create an engine without opening a connection or exposing its password."""
    return create_engine(
        settings.sqlalchemy_database_url(),
        pool_pre_ping=True,
        **engine_options,
    )
