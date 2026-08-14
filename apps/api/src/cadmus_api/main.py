"""FastAPI application composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from cadmus.config import Settings
from cadmus.infrastructure.database import create_database_engine
from fastapi import FastAPI
from sqlalchemy import Engine, text

from cadmus_api.routes.health import create_health_router


def create_app(
    settings: Settings | None = None,
    database_engine: Engine | None = None,
) -> FastAPI:
    """Create an API whose lifespan verifies and owns its database connection."""
    app_settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = database_engine or create_database_engine(app_settings)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        app.state.database_engine = engine
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title=app_settings.name,
        version=app_settings.version,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.include_router(create_health_router(app_settings))
    return app
