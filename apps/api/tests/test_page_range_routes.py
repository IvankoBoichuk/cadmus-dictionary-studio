from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.sources import (
    Dictionary,
    DictionaryAccessError,
    DictionaryPageRange,
    DictionaryStatus,
    GetDictionaryService,
    InspectionStatus,
    PageRangeInput,
    PageRangeSaveOutcome,
    PageRangesUnavailableError,
    PageRangeValidationError,
    SavePageRangesService,
    SourceFile,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


@dataclass
class StubAuthenticationService:
    def login(self, email: str, password: str) -> None:
        raise AssertionError("not used")

    def authenticate(self, token: str) -> User:
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


def _dictionary(**overrides: object) -> Dictionary:
    dictionary_id = overrides.pop("id", uuid4())
    dictionary = Dictionary(
        id=cast(UUID, dictionary_id),
        owner_id=OWNER_ID,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=OWNER_ID,
    )
    for key, value in overrides.items():
        setattr(dictionary, key, value)
    return dictionary


def _source_file(dictionary_id: UUID, **overrides: object) -> SourceFile:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": dictionary_id,
        "original_filename": "dictionary.pdf",
        "mime_type": "application/pdf",
        "byte_size": 1024,
        "checksum_sha256": "a" * 64,
        "storage_key": "sources/owner/key.pdf",
        "uploaded_at": NOW,
        "uploaded_by": OWNER_ID,
        "inspection_status": InspectionStatus.VERIFIED,
        "page_count": 300,
    }
    defaults.update(overrides)
    return SourceFile(**defaults)  # type: ignore[arg-type]


def _page_range(
    dictionary_id: UUID, start: int = 1, end: int = 10
) -> DictionaryPageRange:
    return DictionaryPageRange(
        id=uuid4(),
        dictionary_id=dictionary_id,
        start_page=start,
        end_page=end,
        position=0,
    )


@dataclass
class StubGetDictionaryService:
    dictionary: Dictionary | None = None
    source_file: SourceFile | None = None
    ranges: list[DictionaryPageRange] | None = None
    access_error: DictionaryAccessError | None = None

    def get(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        if self.access_error is not None:
            raise self.access_error
        assert self.dictionary is not None
        return self.dictionary

    def get_source_file(self, dictionary_id: UUID, actor_id: UUID) -> SourceFile:
        if self.access_error is not None:
            raise self.access_error
        if self.source_file is None:
            raise DictionaryAccessError(dictionary_id)
        return self.source_file

    def get_page_ranges(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> list[DictionaryPageRange]:
        if self.access_error is not None:
            raise self.access_error
        return self.ranges or []


@dataclass
class StubSavePageRangesService:
    outcome: PageRangeSaveOutcome | None = None
    error: Exception | None = None

    def save(
        self, dictionary_id: UUID, actor_id: UUID, inputs: list[PageRangeInput]
    ) -> PageRangeSaveOutcome:
        if self.error is not None:
            raise self.error
        assert self.outcome is not None
        return self.outcome


def client_for(
    get_service: StubGetDictionaryService | None = None,
    save_service: StubSavePageRangesService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            get_dictionary_service=cast(
                GetDictionaryService, get_service or StubGetDictionaryService()
            ),
            save_page_ranges_service=cast(
                SavePageRangesService, save_service or StubSavePageRangesService()
            ),
        )
    )


def test_get_page_ranges_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(f"/dictionaries/{uuid4()}/page-ranges")
    assert response.status_code == 401


def test_get_page_ranges_returns_page_count_and_ranges() -> None:
    dictionary = _dictionary()
    service = StubGetDictionaryService(
        dictionary=dictionary,
        source_file=_source_file(dictionary.id, page_count=250),
        ranges=[_page_range(dictionary.id, 10, 220)],
    )

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{dictionary.id}/page-ranges")

    assert response.status_code == 200
    body = response.json()
    assert body["page_count"] == 250
    assert body["ranges"] == [{"start_page": 10, "end_page": 220}]
    assert body["merged"] is False


def test_get_page_ranges_reports_no_page_count_before_a_source_is_verified() -> None:
    dictionary = _dictionary()
    service = StubGetDictionaryService(dictionary=dictionary, source_file=None)

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{dictionary.id}/page-ranges")

    assert response.status_code == 200
    body = response.json()
    assert body["page_count"] is None
    assert body["ranges"] == []


def test_get_page_ranges_not_owned_returns_404() -> None:
    service = StubGetDictionaryService(access_error=DictionaryAccessError(uuid4()))

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/page-ranges")

    assert response.status_code == 404


def test_save_page_ranges_requires_authentication() -> None:
    with client_for() as client:
        response = client.put(
            f"/dictionaries/{uuid4()}/page-ranges", json={"ranges": []}
        )
    assert response.status_code == 401


def test_save_page_ranges_returns_the_normalized_set() -> None:
    dictionary = _dictionary()
    save_service = StubSavePageRangesService(
        outcome=PageRangeSaveOutcome(
            dictionary_id=dictionary.id,
            ranges=[_page_range(dictionary.id, 1, 40)],
            merged=True,
        )
    )
    get_service = StubGetDictionaryService(
        dictionary=dictionary, source_file=_source_file(dictionary.id)
    )

    with client_for(get_service=get_service, save_service=save_service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.put(
            f"/dictionaries/{dictionary.id}/page-ranges",
            json={
                "ranges": [
                    {"start_page": 1, "end_page": 20},
                    {"start_page": 15, "end_page": 40},
                ]
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ranges"] == [{"start_page": 1, "end_page": 40}]
    assert body["merged"] is True


def test_save_page_ranges_returns_field_errors_for_out_of_bounds_pages() -> None:
    save_service = StubSavePageRangesService(
        error=PageRangeValidationError(
            {"ranges.0.end_page": "Кінцева сторінка має бути в межах від 1 до 100."}
        )
    )

    with client_for(save_service=save_service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.put(
            f"/dictionaries/{uuid4()}/page-ranges",
            json={"ranges": [{"start_page": 1, "end_page": 999}]},
        )

    assert response.status_code == 422
    assert "ranges.0.end_page" in response.json()["errors"]


def test_save_page_ranges_rejects_when_page_count_is_unknown() -> None:
    save_service = StubSavePageRangesService(
        error=PageRangesUnavailableError("the PDF's page count is not known yet")
    )

    with client_for(save_service=save_service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.put(
            f"/dictionaries/{uuid4()}/page-ranges",
            json={"ranges": [{"start_page": 1, "end_page": 10}]},
        )

    assert response.status_code == 422
    assert "ranges" in response.json()["errors"]


def test_save_page_ranges_not_owned_returns_404() -> None:
    save_service = StubSavePageRangesService(error=DictionaryAccessError(uuid4()))

    with client_for(save_service=save_service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.put(
            f"/dictionaries/{uuid4()}/page-ranges",
            json={"ranges": [{"start_page": 1, "end_page": 10}]},
        )

    assert response.status_code == 404


def test_save_page_ranges_rejects_pages_below_one_at_the_transport_layer() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.put(
            f"/dictionaries/{uuid4()}/page-ranges",
            json={"ranges": [{"start_page": 0, "end_page": 10}]},
        )

    assert response.status_code == 422
