from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.geography import (
    Area,
    Community,
    CommunityGeometry,
    GeographyQueryService,
    Region,
)
from cadmus.identity import (
    AccountStatus,
    AuthenticationError,
    AuthenticationFailure,
    AuthenticationService,
    User,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

AREA_ID = uuid4()
REGION_ID = uuid4()
COMMUNITY_ID = uuid4()


@dataclass
class StubAuthenticationService:
    def login(self, email: str, password: str) -> None:
        raise AssertionError("not used")

    def authenticate(self, token: str) -> User:
        if token != "token":
            raise AuthenticationError(AuthenticationFailure.INVALID_SESSION)
        return User(
            id=OWNER_ID,
            email="owner@example.com",
            password_hash="not-returned",
            status=AccountStatus.ACTIVE,
            created_at=NOW,
            activated_at=NOW,
        )

    def logout(self, token: str) -> None:
        raise AssertionError("not used")


def _area() -> Area:
    return Area(
        id=AREA_ID, external_id="area-1", name="Львівська область", last_synced_at=NOW
    )


def _region() -> Region:
    return Region(
        id=REGION_ID,
        external_id="region-1",
        name="Львівський район",
        area_id=AREA_ID,
        last_synced_at=NOW,
    )


def _community() -> Community:
    return Community(
        id=COMMUNITY_ID,
        external_id="community-1",
        name="Львівська громада",
        area_id=AREA_ID,
        region_id=REGION_ID,
        last_synced_at=NOW,
        katottg="UA46060000000000000",
        koatuu="4610100000",
        admin_center_name="Львів",
        website="https://city-adm.lviv.ua",
    )


def _geometry() -> CommunityGeometry:
    return CommunityGeometry(
        id=uuid4(),
        community_id=COMMUNITY_ID,
        geometry_type="Point",
        geometry={"type": "Point", "coordinates": [24.03, 49.84]},
        fetched_at=NOW,
    )


@dataclass
class StubGeographyQueryService:
    areas: list[Area] = field(default_factory=lambda: [_area()])
    regions: list[Region] = field(default_factory=lambda: [_region()])
    communities: list[Community] = field(default_factory=lambda: [_community()])
    community: Community | None = field(default_factory=_community)
    geometry: CommunityGeometry | None = None

    def list_areas(self) -> list[Area]:
        return self.areas

    def list_regions(self, area_id: UUID | None = None) -> list[Region]:
        return [r for r in self.regions if area_id is None or r.area_id == area_id]

    def list_communities(
        self, area_id: UUID | None = None, region_id: UUID | None = None
    ) -> list[Community]:
        return [
            c
            for c in self.communities
            if (area_id is None or c.area_id == area_id)
            and (region_id is None or c.region_id == region_id)
        ]

    def get_community(self, community_id: UUID) -> Community | None:
        if self.community is not None and self.community.id == community_id:
            return self.community
        return None

    def get_community_geometry(self, community_id: UUID) -> CommunityGeometry | None:
        if self.geometry is not None and self.geometry.community_id == community_id:
            return self.geometry
        return None


def client_for(
    service: StubGeographyQueryService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            geography_query_service=cast(
                GeographyQueryService, service or StubGeographyQueryService()
            ),
        )
    )


def test_list_areas_requires_authentication() -> None:
    with client_for() as client:
        response = client.get("/geography/areas")
    assert response.status_code == 401


def test_list_areas_returns_synced_areas() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get("/geography/areas")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(AREA_ID)
    assert body[0]["name"] == "Львівська область"


def test_list_regions_filters_by_area() -> None:
    other_area_id = uuid4()
    service = StubGeographyQueryService(
        regions=[
            _region(),
            Region(
                id=uuid4(),
                external_id="region-2",
                name="Other",
                area_id=other_area_id,
                last_synced_at=NOW,
            ),
        ]
    )
    with client_for(service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get("/geography/regions", params={"area_id": str(AREA_ID)})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(REGION_ID)


def test_list_communities_returns_synced_communities() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get("/geography/communities")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["katottg"] == "UA46060000000000000"


def test_get_community_returns_404_when_missing() -> None:
    service = StubGeographyQueryService(community=None)
    with client_for(service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/geography/communities/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_get_community_returns_the_community() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/geography/communities/{COMMUNITY_ID}")
    assert response.status_code == 200
    assert response.json()["name"] == "Львівська громада"


def test_get_community_geo_json_returns_404_when_not_synced() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/geography/communities/{COMMUNITY_ID}/geo_json")
    assert response.status_code == 404


def test_get_community_geo_json_returns_cached_geometry() -> None:
    service = StubGeographyQueryService(geometry=_geometry())
    with client_for(service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/geography/communities/{COMMUNITY_ID}/geo_json")
    assert response.status_code == 200
    body = response.json()
    assert body["geometry_type"] == "Point"
    assert body["geometry"]["coordinates"] == [24.03, 49.84]
