from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import (
    AccountStatus,
    AuthenticationError,
    AuthenticationFailure,
    AuthenticationService,
    User,
)
from cadmus.sources import (
    DictionaryAccessError,
    DictionarySettlementMapping,
    DuplicateSettlementMappingError,
    SettlementConfirmationService,
    SettlementMappingAccessError,
    SettlementMappingCrudService,
    SettlementMappingImportOutcome,
    SettlementMappingImportRowResult,
    SettlementMappingImportService,
    SettlementMappingInput,
    SettlementMappingStatus,
    SettlementMappingValidationError,
    SettlementSearchService,
)
from cadmus.sources.application import SettlementSuggestion
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
STRANGER_ID = uuid4()
DICTIONARY_ID = uuid4()
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


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


def _mapping(**overrides: object) -> DictionarySettlementMapping:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": DICTIONARY_ID,
        "source_label": "Іванівка",
        "status": SettlementMappingStatus.UNRESOLVED,
        "created_at": NOW,
        "updated_at": NOW,
        "created_by": OWNER_ID,
        "updated_by": OWNER_ID,
    }
    defaults.update(overrides)
    return DictionarySettlementMapping(**defaults)  # type: ignore[arg-type]


@dataclass
class StubMappingCrudService:
    mappings: list[DictionarySettlementMapping] = field(default_factory=list)
    owner_id: UUID = OWNER_ID
    dictionary_id: UUID = DICTIONARY_ID
    raise_on_create: Exception | None = None
    raise_on_update: Exception | None = None
    raise_on_bulk_district: Exception | None = None
    bulk_district_updated: int = 3

    def _check_access(self, dictionary_id: UUID, actor_id: UUID) -> None:
        if dictionary_id != self.dictionary_id or actor_id != self.owner_id:
            raise DictionaryAccessError(dictionary_id)

    def list_for_dictionary(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> list[DictionarySettlementMapping]:
        self._check_access(dictionary_id, actor_id)
        return self.mappings

    def create(
        self, dictionary_id: UUID, actor_id: UUID, data: SettlementMappingInput
    ) -> DictionarySettlementMapping:
        self._check_access(dictionary_id, actor_id)
        if self.raise_on_create is not None:
            raise self.raise_on_create
        created = _mapping(source_label=data.source_label)
        self.mappings.append(created)
        return created

    def update(
        self,
        dictionary_id: UUID,
        mapping_id: UUID,
        actor_id: UUID,
        data: SettlementMappingInput,
    ) -> DictionarySettlementMapping:
        self._check_access(dictionary_id, actor_id)
        if self.raise_on_update is not None:
            raise self.raise_on_update
        existing = next((m for m in self.mappings if m.id == mapping_id), None)
        if existing is None:
            raise SettlementMappingAccessError(mapping_id)
        existing.source_note = data.source_note
        return existing

    def delete(self, dictionary_id: UUID, mapping_id: UUID, actor_id: UUID) -> None:
        self._check_access(dictionary_id, actor_id)
        existing = next((m for m in self.mappings if m.id == mapping_id), None)
        if existing is None:
            raise SettlementMappingAccessError(mapping_id)
        self.mappings.remove(existing)

    def set_district_for_community(
        self,
        dictionary_id: UUID,
        community_id: UUID,
        district: str | None,
        actor_id: UUID,
    ) -> int:
        self._check_access(dictionary_id, actor_id)
        if self.raise_on_bulk_district is not None:
            raise self.raise_on_bulk_district
        return self.bulk_district_updated

    def unconfirm(
        self, dictionary_id: UUID, mapping_id: UUID, actor_id: UUID
    ) -> DictionarySettlementMapping:
        self._check_access(dictionary_id, actor_id)
        existing = next((m for m in self.mappings if m.id == mapping_id), None)
        if existing is None:
            raise SettlementMappingAccessError(mapping_id)
        existing.status = SettlementMappingStatus.UNRESOLVED
        existing.confirmed_by = None
        existing.confirmed_at = None
        return existing


@dataclass
class StubSearchService:
    results: list[SettlementSuggestion] = field(default_factory=list)

    def search(
        self,
        *,
        query: str | None = None,
        area_id: UUID | None = None,
        region_id: UUID | None = None,
        community_id: UUID | None = None,
        category: str | None = None,
    ) -> list[SettlementSuggestion]:
        return self.results


@dataclass
class StubConfirmationService:
    confirmed: DictionarySettlementMapping | None = None
    raise_on_confirm: Exception | None = None

    def confirm(
        self, dictionary_id: UUID, mapping_id: UUID, actor_id: UUID
    ) -> DictionarySettlementMapping:
        if self.raise_on_confirm is not None:
            raise self.raise_on_confirm
        assert self.confirmed is not None
        return self.confirmed


@dataclass
class StubImportService:
    preview_results: list[SettlementMappingImportRowResult] = field(
        default_factory=list
    )
    commit_outcome: SettlementMappingImportOutcome = field(
        default_factory=lambda: SettlementMappingImportOutcome(imported=[], skipped=[])
    )

    def preview(
        self, dictionary_id: UUID, actor_id: UUID, raw: bytes, import_format: str
    ) -> list[SettlementMappingImportRowResult]:
        return self.preview_results

    def commit(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        rows: list[SettlementMappingInput],
    ) -> SettlementMappingImportOutcome:
        return self.commit_outcome


def client_for(
    *,
    mapping_crud_service: StubMappingCrudService | None = None,
    search_service: StubSearchService | None = None,
    confirmation_service: StubConfirmationService | None = None,
    import_service: StubImportService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            settlement_mapping_crud_service=cast(
                SettlementMappingCrudService,
                mapping_crud_service or StubMappingCrudService(),
            ),
            settlement_search_service=cast(
                SettlementSearchService, search_service or StubSearchService()
            ),
            settlement_confirmation_service=cast(
                SettlementConfirmationService,
                confirmation_service or StubConfirmationService(),
            ),
            settlement_mapping_import_service=cast(
                SettlementMappingImportService, import_service or StubImportService()
            ),
        )
    )


def test_list_mappings_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(f"/dictionaries/{DICTIONARY_ID}/settlements")
    assert response.status_code == 401


def test_list_mappings_returns_404_for_a_non_owner() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/settlements")
    assert response.status_code == 404


def test_list_mappings_returns_the_dictionarys_mappings() -> None:
    service = StubMappingCrudService(mappings=[_mapping()])
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{DICTIONARY_ID}/settlements")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["source_label"] == "Іванівка"


def test_create_mapping_persists_and_returns_it() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements",
            json={"source_label": "Петрівка"},
        )
    assert response.status_code == 201
    assert response.json()["source_label"] == "Петрівка"


def test_create_mapping_returns_422_on_validation_error() -> None:
    service = StubMappingCrudService(
        raise_on_create=SettlementMappingValidationError(
            {"source_label": "Вкажіть географічну позначку з оригіналу."}
        )
    )
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements",
            json={"source_label": "   "},
        )
    assert response.status_code == 422
    assert "source_label" in response.json()["errors"]


def test_create_mapping_returns_409_on_duplicate() -> None:
    existing_id = uuid4()
    service = StubMappingCrudService(
        raise_on_create=DuplicateSettlementMappingError(existing_id, "Іванівка")
    )
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements",
            json={"source_label": "Іванівка"},
        )
    assert response.status_code == 409
    assert response.json()["mapping_id"] == str(existing_id)


def test_update_mapping_returns_404_when_missing() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{DICTIONARY_ID}/settlements/{uuid4()}",
            json={"source_label": "Іванівка"},
        )
    assert response.status_code == 404


def test_update_mapping_edits_an_existing_entry() -> None:
    existing = _mapping()
    service = StubMappingCrudService(mappings=[existing])
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{DICTIONARY_ID}/settlements/{existing.id}",
            json={"source_label": "Іванівка", "source_note": "уточнення"},
        )
    assert response.status_code == 200
    assert response.json()["source_note"] == "уточнення"


def test_set_district_by_community_reports_the_count() -> None:
    service = StubMappingCrudService(mappings=[_mapping()], bulk_district_updated=4)
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements/district-by-community",
            json={"community_id": str(uuid4()), "district": "Хот."},
        )
    assert response.status_code == 200
    assert response.json() == {"updated": 4}


def test_set_district_by_community_returns_404_for_a_foreign_dictionary() -> None:
    service = StubMappingCrudService(
        raise_on_bulk_district=DictionaryAccessError(DICTIONARY_ID)
    )
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements/district-by-community",
            json={"community_id": str(uuid4()), "district": "Хот."},
        )
    assert response.status_code == 404


def test_delete_mapping_removes_it() -> None:
    existing = _mapping()
    service = StubMappingCrudService(mappings=[existing])
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.delete(
            f"/dictionaries/{DICTIONARY_ID}/settlements/{existing.id}"
        )
    assert response.status_code == 204
    assert service.mappings == []


def test_delete_mapping_returns_404_when_missing() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.delete(f"/dictionaries/{DICTIONARY_ID}/settlements/{uuid4()}")
    assert response.status_code == 404


def test_confirm_mapping_returns_the_confirmed_entry() -> None:
    confirmed = _mapping(
        status=SettlementMappingStatus.CONFIRMED,
        confirmed_by=OWNER_ID,
        confirmed_at=NOW,
    )
    service = StubConfirmationService(confirmed=confirmed)
    with client_for(confirmation_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements/{confirmed.id}/confirm"
        )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_confirm_mapping_returns_422_when_unlinked() -> None:
    service = StubConfirmationService(
        raise_on_confirm=SettlementMappingValidationError(
            {"settlement_id": "Спершу оберіть населений пункт."}
        )
    )
    with client_for(confirmation_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements/{uuid4()}/confirm"
        )
    assert response.status_code == 422


def test_unconfirm_mapping_reverts_status() -> None:
    existing = _mapping(
        status=SettlementMappingStatus.CONFIRMED,
        confirmed_by=OWNER_ID,
        confirmed_at=NOW,
    )
    service = StubMappingCrudService(mappings=[existing])
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements/{existing.id}/unconfirm"
        )
    assert response.status_code == 200
    assert response.json()["status"] == "unresolved"


def test_search_settlements_requires_dictionary_ownership() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/settlements/search")
    assert response.status_code == 404


def test_search_settlements_returns_suggestions() -> None:
    suggestion = SettlementSuggestion(
        settlement_id=uuid4(),
        title="Іванівка",
        category="село",
        community_id=uuid4(),
        community_name="Львівська громада",
        region_id=uuid4(),
        area_id=uuid4(),
    )
    service = StubSearchService(results=[suggestion])
    with client_for(search_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(
            f"/dictionaries/{DICTIONARY_ID}/settlements/search",
            params={"query": "Іван"},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Іванівка"


def test_import_preview_reports_rows() -> None:
    service = StubImportService(
        preview_results=[
            SettlementMappingImportRowResult(
                row_number=1,
                input=SettlementMappingInput(
                    source_label="Іванівка",
                    source_note=None,
                    district=None,
                    modern_settlement_name=None,
                    settlement_category=None,
                    settlement_id=None,
                    status=SettlementMappingStatus.UNRESOLVED,
                ),
                errors={},
            )
        ]
    )
    with client_for(import_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        csv_body = b"source_label\nsettlement label\n"
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements/import/preview",
            files={"file": ("labels.csv", csv_body, "text/csv")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["valid_count"] == 1
    assert body["error_count"] == 0


def test_import_commit_returns_imported_and_skipped_rows() -> None:
    imported = _mapping()
    skipped = SettlementMappingImportRowResult(
        row_number=2, input=None, errors={"source_label": "required"}
    )
    service = StubImportService(
        commit_outcome=SettlementMappingImportOutcome(
            imported=[imported], skipped=[skipped]
        )
    )
    with client_for(import_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{DICTIONARY_ID}/settlements/import/commit",
            json={"rows": [{"source_label": "Іванівка"}]},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["imported"]) == 1
    assert len(body["skipped"]) == 1


def test_export_defaults_to_json() -> None:
    service = StubMappingCrudService(mappings=[_mapping()])
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{DICTIONARY_ID}/settlements/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_export_csv_returns_a_csv_attachment() -> None:
    service = StubMappingCrudService(mappings=[_mapping()])
    with client_for(mapping_crud_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(
            f"/dictionaries/{DICTIONARY_ID}/settlements/export",
            params={"format": "csv"},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
