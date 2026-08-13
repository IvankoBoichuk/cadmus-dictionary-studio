"""API liveness route."""

from typing import Literal

from cadmus.config import Settings
from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Stable response contract for API liveness."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"] = "ok"
    service: str
    version: str


def create_health_router(settings: Settings) -> APIRouter:
    """Create the health router using application metadata."""
    router = APIRouter(tags=["health"])

    @router.get(
        "/health",
        response_model=HealthResponse,
        status_code=status.HTTP_200_OK,
        summary="Check API liveness",
    )
    async def get_health() -> HealthResponse:
        return HealthResponse(service=settings.name, version=settings.version)

    return router
