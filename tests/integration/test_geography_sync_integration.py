"""Full BH-30 geography flow against real PostgreSQL (AC14).

Sync -> create dictionary -> add a geographic label -> search the local
cache -> confirm the mapping -> verify persisted provenance. The
``decentralization.ua`` client is a small in-memory fake -- this test never
makes a live network call.
"""

import os
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from cadmus.config import Settings
from cadmus.geography import GeographyQueryService, SyncGeographyService
from cadmus.infrastructure.geography import create_geography_unit_of_work_factory
from cadmus.infrastructure.object_storage import create_object_storage
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.sources import (
    SettlementConfirmationService,
    SettlementMappingCrudService,
    SettlementMappingInput,
    SettlementMappingStatus,
    SettlementSearchService,
    SourceInspectionQueueUnavailableError,
    UploadDictionaryService,
)
from sqlalchemy import Engine, create_engine, text

pytestmark = pytest.mark.integration

VALID_PDF = Path("fixtures/dictionaries/sample-dictionary.pdf").read_bytes()

AREA: dict[str, object] = {"id": "area-1", "title": "Львівська область"}
REGION: dict[str, object] = {
    "id": "region-1",
    "title": "Львівський район",
    "area_id": "area-1",
}
COMMUNITY: dict[str, object] = {
    "id": "community-1",
    "title": "Львівська громада",
    "area_id": "area-1",
    "region_id": "region-1",
    "katottg": "UA46060000000000000",
    "koatuu": "4610100000",
    "villages": [{"title": "Іванівка", "category": "село"}],
}


class FakeDecentralizationApiClient:
    """A tiny fixture-backed stand-in -- no real network call is ever made."""

    def list_areas(self) -> list[dict[str, object]]:
        return [AREA]

    def get_area(self, external_id: str) -> dict[str, object] | None:
        return AREA if external_id == AREA["id"] else None

    def list_regions(self) -> list[dict[str, object]]:
        return [REGION]

    def get_region(self, external_id: str) -> dict[str, object] | None:
        return REGION if external_id == REGION["id"] else None

    def list_communities(self) -> list[dict[str, object]]:
        return [COMMUNITY]

    def get_community(self, external_id: str) -> dict[str, object] | None:
        return COMMUNITY if external_id == COMMUNITY["id"] else None

    def get_community_geo_json(self, community_id: str) -> dict[str, object] | None:
        return None


class NoOpInspectionQueue:
    """A stand-in queue: the worker/Redis are not part of this test profile."""

    def enqueue_inspection(self, source_file_id: object) -> None:
        raise SourceInspectionQueueUnavailableError("no worker in this test profile")


def _prepare_database() -> str:
    database_url = os.environ["CADMUS_TEST_DATABASE_URL"]
    os.environ["CADMUS_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM cadmus.dictionary_settlement_mappings"))
        connection.execute(text("DELETE FROM cadmus.dictionary_events"))
        connection.execute(text("DELETE FROM cadmus.dictionary_pages"))
        connection.execute(text("DELETE FROM cadmus.dictionary_source_files"))
        connection.execute(text("DELETE FROM cadmus.dictionary_contributors"))
        connection.execute(text("DELETE FROM cadmus.dictionary_languages"))
        connection.execute(text("DELETE FROM cadmus.dictionaries"))
        connection.execute(text("DELETE FROM cadmus.authenticated_sessions"))
        connection.execute(text("DELETE FROM cadmus.email_verification_tokens"))
        connection.execute(text("DELETE FROM cadmus.users"))
        connection.execute(text("DELETE FROM cadmus.geography_sync_runs"))
        connection.execute(text("DELETE FROM cadmus.geography_community_geometries"))
        connection.execute(text("DELETE FROM cadmus.geography_settlements"))
        connection.execute(text("DELETE FROM cadmus.geography_communities"))
        connection.execute(text("DELETE FROM cadmus.geography_regions"))
        connection.execute(text("DELETE FROM cadmus.geography_areas"))
    engine.dispose()
    return database_url


def _create_user(engine: Engine, email: str) -> UUID:
    user_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cadmus.users "
                "(id, email, password_hash, status, created_at) "
                "VALUES (:id, :email, 'not-used', 'active', now())"
            ),
            {"id": user_id, "email": email},
        )
    return user_id


def test_sync_then_match_and_confirm_a_settlement_mapping() -> None:
    database_url = _prepare_database()
    engine = create_engine(database_url)
    owner_id = _create_user(engine, f"owner-{uuid4()}@example.com")
    settings = Settings()
    sources_unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    geography_unit_of_work_factory = create_geography_unit_of_work_factory(engine)
    object_storage = create_object_storage(settings)

    sync_service = SyncGeographyService(
        unit_of_work_factory=geography_unit_of_work_factory,
        client=FakeDecentralizationApiClient(),
    )
    geography_query_service = GeographyQueryService(
        unit_of_work_factory=geography_unit_of_work_factory
    )
    upload_service = UploadDictionaryService(
        unit_of_work_factory=sources_unit_of_work_factory,
        object_storage=object_storage,
        inspection_queue=NoOpInspectionQueue(),
        max_upload_size_bytes=10 * 1024 * 1024,
    )
    mapping_crud_service = SettlementMappingCrudService(
        unit_of_work_factory=sources_unit_of_work_factory,
        geography_unit_of_work_factory=geography_unit_of_work_factory,
    )
    search_service = SettlementSearchService(
        geography_unit_of_work_factory=geography_unit_of_work_factory
    )
    confirmation_service = SettlementConfirmationService(
        unit_of_work_factory=sources_unit_of_work_factory,
        geography_unit_of_work_factory=geography_unit_of_work_factory,
    )

    outcome = None
    try:
        # 1. Sync areas/regions/communities+settlements from the (fake)
        # decentralization.ua API into the local cache.
        summary = sync_service.sync_all()
        assert summary.areas.records_synced == 1
        assert summary.regions.records_synced == 1
        assert summary.communities.records_synced == 1

        communities = geography_query_service.list_communities()
        assert len(communities) == 1
        community = communities[0]
        assert community.katottg == "UA46060000000000000"

        # 2. Create a dictionary that will hold the geographic label.
        outcome = upload_service.upload(
            owner_id, "Словник.pdf", "application/pdf", BytesIO(VALID_PDF)
        )
        dictionary_id = outcome.dictionary.id

        # 3. Record the original geographic label from the source text.
        created = mapping_crud_service.create(
            dictionary_id,
            owner_id,
            SettlementMappingInput(
                source_label="Історична Іванувка",
                source_note="стара форма з тексту",
                modern_settlement_name=None,
                settlement_category=None,
                settlement_id=None,
                status=SettlementMappingStatus.UNRESOLVED,
            ),
        )
        assert created.status is SettlementMappingStatus.UNRESOLVED

        # 4. Search the local cache for a modern settlement match (AC8) --
        # never a live call to decentralization.ua.
        suggestions = search_service.search(
            query="Іванівка",
            area_id=None,
            region_id=None,
            community_id=None,
            category=None,
        )
        assert len(suggestions) == 1
        suggestion = suggestions[0]
        assert suggestion.community_name == "Львівська громада"

        # Picking a suggestion links the settlement and marks it suggested,
        # but does NOT confirm it (AC9: only the confirmation service can).
        linked = mapping_crud_service.update(
            dictionary_id,
            created.id,
            owner_id,
            SettlementMappingInput(
                source_label="Історична Іванувка",
                source_note="стара форма з тексту",
                modern_settlement_name=suggestion.title,
                settlement_category=suggestion.category,
                settlement_id=suggestion.settlement_id,
                status=SettlementMappingStatus.SUGGESTED,
            ),
        )
        assert linked.status is SettlementMappingStatus.SUGGESTED
        assert linked.confirmed_at is None

        # 5. Confirm the mapping -- the only path that snapshots the
        # hierarchy and sets confirmation provenance (AC10).
        confirmed = confirmation_service.confirm(dictionary_id, created.id, owner_id)

        assert confirmed.status is SettlementMappingStatus.CONFIRMED
        assert confirmed.confirmed_by == owner_id
        assert confirmed.confirmed_at is not None
        assert confirmed.area_name == "Львівська область"
        assert confirmed.region_name == "Львівський район"
        assert confirmed.community_name == "Львівська громада"
        assert confirmed.external_community_id == "community-1"
        assert confirmed.katottg == "UA46060000000000000"
        assert confirmed.koatuu == "4610100000"
        # The original historical form is untouched by confirmation (AC7).
        assert confirmed.source_label == "Історична Іванувка"

        # 6. The confirmed mapping is queryable back out with full
        # provenance intact, independent of the request that confirmed it.
        persisted = mapping_crud_service.list_for_dictionary(dictionary_id, owner_id)
        assert len(persisted) == 1
        assert persisted[0].id == created.id
        # This mapping was reloaded fresh from PostgreSQL (unlike the
        # objects above, which are the same in-memory instance the service
        # mutated), so compare by value rather than identity.
        assert persisted[0].status == SettlementMappingStatus.CONFIRMED
        assert persisted[0].katottg == "UA46060000000000000"

        with engine.connect() as connection:
            stored = connection.execute(
                text(
                    "SELECT status, confirmed_by, katottg, koatuu "
                    "FROM cadmus.dictionary_settlement_mappings WHERE id = :id"
                ),
                {"id": created.id},
            ).one()
        assert stored.status == "confirmed"
        assert stored.confirmed_by == owner_id
        assert stored.katottg == "UA46060000000000000"
        assert stored.koatuu == "4610100000"

        # 7. A later resync must not mutate the already-confirmed snapshot
        # (AC10, AC12), even though the reference data itself re-upserts.
        sync_service.sync_all()
        unaffected = mapping_crud_service.list_for_dictionary(dictionary_id, owner_id)
        assert unaffected[0].community_name == "Львівська громада"
        assert unaffected[0].confirmed_by == owner_id
    finally:
        if outcome is not None:
            object_storage.delete(outcome.source_file.storage_key)
        engine.dispose()
