"""BH-53: HTTP adapter tests for the dictionary page-viewer routes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.sources import (
    DictionaryAccessError,
    DictionaryPage,
    GetDictionaryService,
    ObjectStorage,
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


def _page(
    source_file_id: UUID, page_index: int, key: str = "sources/x/pages/0.png"
) -> DictionaryPage:
    return DictionaryPage(
        id=uuid4(),
        source_file_id=source_file_id,
        page_index=page_index,
        processed_asset_key=key,
        width=1000,
        height=1400,
        checksum_sha256="b" * 64,
        created_at=NOW,
    )


@dataclass
class StubGetDictionaryService:
    total_pages: int = 0
    page: DictionaryPage | None = None
    access_error: DictionaryAccessError | None = None

    def count_viewable_pages(self, dictionary_id: UUID, actor_id: UUID) -> int:
        if self.access_error is not None:
            raise self.access_error
        return self.total_pages

    def get_viewable_page(
        self, dictionary_id: UUID, actor_id: UUID, ordinal: int
    ) -> DictionaryPage | None:
        if self.access_error is not None:
            raise self.access_error
        return self.page


class StubObjectStorage:
    def __init__(self, content: bytes = b"\x89PNG\r\n\x1a\nrest") -> None:
        self._content = content

    def upload(self, key: str, source: object, length: int, content_type: str) -> None:
        raise AssertionError("not used")

    def download(self, key: str, destination: object) -> None:
        destination.write(self._content)  # type: ignore[attr-defined]

    def delete(self, key: str) -> None:
        raise AssertionError("not used")

    def delete_prefix(self, prefix: str) -> None:
        raise AssertionError("not used")


def client_for(
    get_service: StubGetDictionaryService | None = None,
    object_storage: StubObjectStorage | None = None,
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
            object_storage=cast(ObjectStorage, object_storage or StubObjectStorage()),
        )
    )


def test_get_summary_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(f"/dictionaries/{uuid4()}/pages")
    assert response.status_code == 401


def test_get_summary_returns_the_viewable_page_count() -> None:
    service = StubGetDictionaryService(total_pages=42)

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages")

    assert response.status_code == 200
    assert response.json() == {"total_pages": 42}


def test_get_summary_not_owned_returns_404() -> None:
    service = StubGetDictionaryService(access_error=DictionaryAccessError(uuid4()))

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages")

    assert response.status_code == 404


def test_get_page_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(f"/dictionaries/{uuid4()}/pages/1")
    assert response.status_code == 401


def test_get_page_streams_the_image_with_a_derived_content_type() -> None:
    page = _page(uuid4(), 0, key="sources/x/pages/00000.png")
    service = StubGetDictionaryService(page=page)

    with client_for(
        get_service=service, object_storage=StubObjectStorage(b"\x89PNG\r\n\x1a\nrest")
    ) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/1")

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n\x1a\nrest"
    assert response.headers["content-type"] == "image/png"


def test_get_page_streams_a_jpg_page_as_image_jpeg() -> None:
    page = _page(uuid4(), 0, key="sources/x/pages/00000.jpg")
    service = StubGetDictionaryService(page=page)

    with client_for(
        get_service=service, object_storage=StubObjectStorage(b"\xff\xd8")
    ) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_get_page_out_of_range_returns_404() -> None:
    service = StubGetDictionaryService(page=None)

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/999")

    assert response.status_code == 404


def test_get_page_not_owned_returns_404() -> None:
    service = StubGetDictionaryService(access_error=DictionaryAccessError(uuid4()))

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/1")

    assert response.status_code == 404


def test_get_page_rejects_a_non_positive_page_number() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/0")

    assert response.status_code == 422
