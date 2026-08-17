"""Thin HTTP adapters for the BH-30 geography reference-data read model.

Every route here is read-only against the local sync cache: none of them
ever call the external ``decentralization.ua`` client inline (AC15/AC16).
Any authenticated user may browse this data -- it is shared reference data,
not owned by a dictionary or a user.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.geography import (
    Area,
    Community,
    CommunityGeometry,
    GeographyQueryService,
    Region,
)
from cadmus.identity import AuthenticationError, AuthenticationService, User
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

SESSION_COOKIE_NAME = "cadmus_session"


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class AreaResponse(BaseModel):
    """One synced oblast."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    external_id: str
    name: str


class RegionResponse(BaseModel):
    """One synced raion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    external_id: str
    name: str
    area_id: UUID


class CommunityResponse(BaseModel):
    """One synced territorial hromada."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    external_id: str
    name: str
    area_id: UUID
    region_id: UUID
    katottg: str | None
    koatuu: str | None
    admin_center_name: str | None
    website: str | None


class CommunityGeometryResponse(BaseModel):
    """One community's cached GeoJSON geometry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    community_id: UUID
    geometry_type: str
    geometry: dict[str, object]
    fetched_at: datetime


UNAUTHORIZED_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "The browser has no valid session",
    }
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "The requested reference-data record does not exist",
    }
}


def _area_response(area: Area) -> AreaResponse:
    return AreaResponse(id=area.id, external_id=area.external_id, name=area.name)


def _region_response(region: Region) -> RegionResponse:
    return RegionResponse(
        id=region.id,
        external_id=region.external_id,
        name=region.name,
        area_id=region.area_id,
    )


def _community_response(community: Community) -> CommunityResponse:
    return CommunityResponse(
        id=community.id,
        external_id=community.external_id,
        name=community.name,
        area_id=community.area_id,
        region_id=community.region_id,
        katottg=community.katottg,
        koatuu=community.koatuu,
        admin_center_name=community.admin_center_name,
        website=community.website,
    )


def _geometry_response(geometry: CommunityGeometry) -> CommunityGeometryResponse:
    return CommunityGeometryResponse(
        id=geometry.id,
        community_id=geometry.community_id,
        geometry_type=geometry.geometry_type,
        geometry=geometry.geometry,
        fetched_at=geometry.fetched_at,
    )


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"code": "not_found", "message": message},
    )


def create_geography_router(
    authentication_service: AuthenticationService,
    geography_query_service: GeographyQueryService,
) -> APIRouter:
    """Create BH-30 geography reference-data browsing routes."""
    router = APIRouter(prefix="/geography", tags=["geography"])

    def current_user(
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> User:
        if session_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_session", "message": "Потрібна авторизація."},
            )
        try:
            return authentication_service.authenticate(session_token)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": error.reason, "message": "Потрібна авторизація."},
            ) from error

    AuthenticatedUser = Annotated[User, Depends(current_user)]

    @router.get(
        "/areas",
        response_model=list[AreaResponse],
        responses={**UNAUTHORIZED_RESPONSE},
        summary="List every synced area (oblast)",
    )
    def list_areas(user: AuthenticatedUser) -> list[AreaResponse]:
        return [_area_response(area) for area in geography_query_service.list_areas()]

    @router.get(
        "/regions",
        response_model=list[RegionResponse],
        responses={**UNAUTHORIZED_RESPONSE},
        summary="List every synced region (raion), optionally filtered by area",
    )
    def list_regions(
        user: AuthenticatedUser,
        area_id: Annotated[UUID | None, Query()] = None,
    ) -> list[RegionResponse]:
        return [
            _region_response(region)
            for region in geography_query_service.list_regions(area_id)
        ]

    @router.get(
        "/communities",
        response_model=list[CommunityResponse],
        responses={**UNAUTHORIZED_RESPONSE},
        summary=(
            "List every synced community (hromada), optionally filtered by area "
            "and/or region"
        ),
    )
    def list_communities(
        user: AuthenticatedUser,
        area_id: Annotated[UUID | None, Query()] = None,
        region_id: Annotated[UUID | None, Query()] = None,
    ) -> list[CommunityResponse]:
        return [
            _community_response(community)
            for community in geography_query_service.list_communities(
                area_id, region_id
            )
        ]

    @router.get(
        "/communities/{community_id}",
        response_model=CommunityResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Get one synced community by its local id",
    )
    def get_community(
        user: AuthenticatedUser, community_id: Annotated[UUID, Path()]
    ) -> CommunityResponse | JSONResponse:
        community = geography_query_service.get_community(community_id)
        if community is None:
            return _not_found("Громаду не знайдено.")
        return _community_response(community)

    @router.get(
        "/communities/{community_id}/geo_json",
        response_model=CommunityGeometryResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Get one community's cached GeoJSON geometry",
    )
    def get_community_geo_json(
        user: AuthenticatedUser, community_id: Annotated[UUID, Path()]
    ) -> CommunityGeometryResponse | JSONResponse:
        geometry = geography_query_service.get_community_geometry(community_id)
        if geometry is None:
            return _not_found("Геометрію громади ще не синхронізовано.")
        return _geometry_response(geometry)

    return router
