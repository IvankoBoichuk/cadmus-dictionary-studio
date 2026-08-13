"""FastAPI application composition root."""

from cadmus.config import Settings
from fastapi import FastAPI

from cadmus_api.routes.health import create_health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an API application without opening external connections."""
    app_settings = settings if settings is not None else Settings()
    app = FastAPI(title=app_settings.name, version=app_settings.version)
    app.state.settings = app_settings
    app.include_router(create_health_router(app_settings))
    return app
