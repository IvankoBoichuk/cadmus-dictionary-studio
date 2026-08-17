"""Application-owned ports for the geography reference-data module."""

from collections.abc import Callable, Sequence
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.geography.domain import (
    Area,
    Community,
    CommunityGeometry,
    Region,
    Settlement,
    SyncRun,
)


class DecentralizationApiError(RuntimeError):
    """Base error for ``decentralization.ua`` client failures."""


class DecentralizationApiUnavailableError(DecentralizationApiError):
    """Raised when the API cannot be reached after exhausting retries."""


class DecentralizationApiResponseError(DecentralizationApiError):
    """Raised on a non-retryable client error: a 4xx status or a malformed
    (non-JSON, wrong-shape) response body.
    """


class DecentralizationApiClient(Protocol):
    """Outbound boundary for ``decentralization.ua``'s GraphQL and REST API."""

    def list_areas(self) -> list[dict[str, object]]: ...

    def get_area(self, external_id: str) -> dict[str, object] | None: ...

    def list_regions(self) -> list[dict[str, object]]: ...

    def get_region(self, external_id: str) -> dict[str, object] | None: ...

    def list_communities(self) -> list[dict[str, object]]: ...

    def get_community(self, external_id: str) -> dict[str, object] | None: ...

    def get_community_geo_json(self, community_id: str) -> dict[str, object] | None: ...


class GeographyRepository(Protocol):
    """Persistence operations for the local geography reference-data cache."""

    def upsert_area(self, area: Area) -> None: ...

    def upsert_region(self, region: Region) -> None: ...

    def upsert_community(
        self, community: Community, settlements: Sequence[Settlement]
    ) -> None: ...

    def upsert_geometry(self, geometry: CommunityGeometry) -> None: ...

    def find_area_by_external_id(self, external_id: str) -> Area | None: ...

    def find_region_by_external_id(self, external_id: str) -> Region | None: ...

    def find_community_by_external_id(self, external_id: str) -> Community | None: ...

    def get_area(self, area_id: UUID) -> Area | None: ...

    def get_region(self, region_id: UUID) -> Region | None: ...

    def get_settlement(self, settlement_id: UUID) -> Settlement | None: ...

    def list_areas(self) -> list[Area]: ...

    def list_regions(self, area_id: UUID | None = None) -> list[Region]: ...

    def list_communities(
        self, area_id: UUID | None = None, region_id: UUID | None = None
    ) -> list[Community]: ...

    def search_settlements(
        self,
        *,
        query: str | None,
        area_id: UUID | None,
        region_id: UUID | None,
        community_id: UUID | None,
        category: str | None,
        limit: int = 25,
    ) -> list[tuple[Settlement, Community]]: ...

    def get_community(self, community_id: UUID) -> Community | None: ...

    def get_community_geometry(
        self, community_id: UUID
    ) -> CommunityGeometry | None: ...

    def add_sync_run(self, run: SyncRun) -> None: ...


class GeographyUnitOfWork(Protocol):
    """Transaction boundary controlled by a geography use case."""

    @property
    def geography(self) -> GeographyRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type GeographyUnitOfWorkFactory = Callable[[], GeographyUnitOfWork]
