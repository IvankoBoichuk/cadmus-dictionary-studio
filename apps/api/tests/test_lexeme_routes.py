"""BH-54: HTTP adapter tests for the manual lexeme-selection routes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.lexicography import (
    CreateLexemeService,
    DeleteLexemeService,
    DuplicateLexemeError,
    Lexeme,
    LexemeAccessError,
    LexemeInput,
    LexemeNotFoundError,
    LexemeOrigin,
    LexemePageNotFoundError,
    LexemeQueryService,
    LexemeValidationError,
    UpdateLexemeInput,
    UpdateLexemeService,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


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


def _lexeme(**overrides: object) -> Lexeme:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": uuid4(),
        "page_id": uuid4(),
        "source_text": "слово",
        "x": 10.0,
        "y": 10.0,
        "width": 100.0,
        "height": 40.0,
        "origin": LexemeOrigin.MANUAL,
        "created_at": NOW,
        "created_by": OWNER_ID,
        "updated_at": NOW,
        "updated_by": OWNER_ID,
    }
    defaults.update(overrides)
    return Lexeme(**defaults)  # type: ignore[arg-type]


@dataclass
class StubCreateLexemeService:
    lexeme: Lexeme | None = None
    error: Exception | None = None
    received: LexemeInput | None = None

    def create(self, dictionary_id: UUID, actor_id: UUID, data: LexemeInput) -> Lexeme:
        self.received = data
        if self.error is not None:
            raise self.error
        assert self.lexeme is not None
        return self.lexeme


@dataclass
class StubLexemeQueryService:
    lexemes: list[Lexeme] | None = None
    error: Exception | None = None

    def list_for_page(
        self, dictionary_id: UUID, actor_id: UUID, page_number: int
    ) -> list[Lexeme]:
        if self.error is not None:
            raise self.error
        return self.lexemes or []


@dataclass
class StubUpdateLexemeService:
    lexeme: Lexeme | None = None
    error: Exception | None = None
    received: UpdateLexemeInput | None = None

    def update(
        self,
        dictionary_id: UUID,
        lexeme_id: UUID,
        actor_id: UUID,
        data: UpdateLexemeInput,
    ) -> Lexeme:
        self.received = data
        if self.error is not None:
            raise self.error
        assert self.lexeme is not None
        return self.lexeme


@dataclass
class StubDeleteLexemeService:
    error: Exception | None = None
    deleted: tuple[UUID, UUID, UUID] | None = None

    def delete(self, dictionary_id: UUID, lexeme_id: UUID, actor_id: UUID) -> None:
        self.deleted = (dictionary_id, lexeme_id, actor_id)
        if self.error is not None:
            raise self.error


def client_for(
    create_service: StubCreateLexemeService | None = None,
    query_service: StubLexemeQueryService | None = None,
    update_service: StubUpdateLexemeService | None = None,
    delete_service: StubDeleteLexemeService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            create_lexeme_service=cast(
                CreateLexemeService, create_service or StubCreateLexemeService()
            ),
            lexeme_query_service=cast(
                LexemeQueryService, query_service or StubLexemeQueryService()
            ),
            update_lexeme_service=cast(
                UpdateLexemeService, update_service or StubUpdateLexemeService()
            ),
            delete_lexeme_service=cast(
                DeleteLexemeService, delete_service or StubDeleteLexemeService()
            ),
        )
    )


def test_create_lexeme_requires_authentication() -> None:
    with client_for() as client:
        response = client.post(
            f"/dictionaries/{uuid4()}/pages/1/lexemes",
            json={"source_text": "слово", "x": 0, "y": 0, "width": 10, "height": 10},
        )
    assert response.status_code == 401


def test_create_lexeme_returns_the_persisted_lexeme() -> None:
    lexeme = _lexeme(source_text="слово")
    service = StubCreateLexemeService(lexeme=lexeme)

    with client_for(create_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{uuid4()}/pages/1/lexemes",
            json={"source_text": "слово", "x": 10, "y": 10, "width": 100, "height": 40},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(lexeme.id)
    assert body["origin"] == "manual"
    assert service.received is not None
    assert service.received.page_number == 1
    assert service.received.confirm_duplicate is False
    assert service.received.origin == LexemeOrigin.MANUAL


def test_create_lexeme_passes_through_an_explicit_ocr_origin() -> None:
    lexeme = _lexeme(source_text="слово", origin=LexemeOrigin.OCR)
    service = StubCreateLexemeService(lexeme=lexeme)

    with client_for(create_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{uuid4()}/pages/1/lexemes",
            json={
                "source_text": "слово",
                "x": 10,
                "y": 10,
                "width": 100,
                "height": 40,
                "origin": "ocr",
            },
        )

    assert response.status_code == 201
    assert response.json()["origin"] == "ocr"
    assert service.received is not None
    assert service.received.origin == LexemeOrigin.OCR


def test_create_lexeme_passes_through_a_second_box() -> None:
    lexeme = _lexeme(source_text="слово", x2=600, y2=10, width2=90, height2=40)
    service = StubCreateLexemeService(lexeme=lexeme)

    with client_for(create_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{uuid4()}/pages/1/lexemes",
            json={
                "source_text": "слово",
                "x": 10,
                "y": 10,
                "width": 100,
                "height": 40,
                "x2": 600,
                "y2": 10,
                "width2": 90,
                "height2": 40,
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert (body["x2"], body["y2"], body["width2"], body["height2"]) == (
        600,
        10,
        90,
        40,
    )
    assert service.received is not None
    assert (
        service.received.x2,
        service.received.y2,
        service.received.width2,
        service.received.height2,
    ) == (600, 10, 90, 40)


def test_create_lexeme_rejects_a_non_positive_bounding_box() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{uuid4()}/pages/1/lexemes",
            json={"source_text": "слово", "x": 0, "y": 0, "width": 0, "height": 10},
        )

    assert response.status_code == 422


def test_create_lexeme_returns_field_errors_for_invalid_bounds() -> None:
    service = StubCreateLexemeService(
        error=LexemeValidationError({"width": "Виділена область виходить за межі."})
    )

    with client_for(create_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{uuid4()}/pages/1/lexemes",
            json={"source_text": "слово", "x": 0, "y": 0, "width": 10, "height": 10},
        )

    assert response.status_code == 422
    assert "width" in response.json()["errors"]


def test_create_lexeme_not_owned_or_page_missing_returns_404() -> None:
    for error in (LexemeAccessError(uuid4()), LexemePageNotFoundError(uuid4(), 1)):
        service = StubCreateLexemeService(error=error)
        with client_for(create_service=service) as client:
            client.cookies.set("cadmus_session", "token")
            response = client.post(
                f"/dictionaries/{uuid4()}/pages/1/lexemes",
                json={
                    "source_text": "слово",
                    "x": 0,
                    "y": 0,
                    "width": 10,
                    "height": 10,
                },
            )
        assert response.status_code == 404


def test_create_lexeme_reports_a_duplicate_overlap_as_409() -> None:
    existing_id = uuid4()
    service = StubCreateLexemeService(error=DuplicateLexemeError(existing_id))

    with client_for(create_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/dictionaries/{uuid4()}/pages/1/lexemes",
            json={"source_text": "слово", "x": 0, "y": 0, "width": 10, "height": 10},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "duplicate_lexeme"
    assert body["existing_lexeme_id"] == str(existing_id)


def test_create_lexeme_passes_through_confirm_duplicate() -> None:
    lexeme = _lexeme()
    service = StubCreateLexemeService(lexeme=lexeme)

    with client_for(create_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        client.post(
            f"/dictionaries/{uuid4()}/pages/1/lexemes",
            json={
                "source_text": "слово",
                "x": 0,
                "y": 0,
                "width": 10,
                "height": 10,
                "confirm_duplicate": True,
            },
        )

    assert service.received is not None
    assert service.received.confirm_duplicate is True


def test_list_lexemes_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(f"/dictionaries/{uuid4()}/pages/1/lexemes")
    assert response.status_code == 401


def test_list_lexemes_returns_the_page_s_lexemes() -> None:
    lexeme = _lexeme(source_text="перше")
    service = StubLexemeQueryService(lexemes=[lexeme])

    with client_for(query_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/1/lexemes")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["source_text"] == "перше"


def test_list_lexemes_not_owned_or_page_missing_returns_404() -> None:
    for error in (LexemeAccessError(uuid4()), LexemePageNotFoundError(uuid4(), 1)):
        service = StubLexemeQueryService(error=error)
        with client_for(query_service=service) as client:
            client.cookies.set("cadmus_session", "token")
            response = client.get(f"/dictionaries/{uuid4()}/pages/1/lexemes")
        assert response.status_code == 404


def test_update_lexeme_requires_authentication() -> None:
    with client_for() as client:
        response = client.patch(
            f"/dictionaries/{uuid4()}/lexemes/{uuid4()}",
            json={"source_text": "слово", "x": 0, "y": 0, "width": 10, "height": 10},
        )
    assert response.status_code == 401


def test_update_lexeme_returns_the_updated_lexeme() -> None:
    lexeme = _lexeme(source_text="нове")
    service = StubUpdateLexemeService(lexeme=lexeme)

    with client_for(update_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{uuid4()}/lexemes/{lexeme.id}",
            json={"source_text": "нове", "x": 20, "y": 20, "width": 120, "height": 50},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_text"] == "нове"
    assert service.received is not None
    assert service.received.source_text == "нове"


def test_update_lexeme_passes_through_a_second_box() -> None:
    lexeme = _lexeme(source_text="слово", x2=600, y2=10, width2=90, height2=40)
    service = StubUpdateLexemeService(lexeme=lexeme)

    with client_for(update_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{uuid4()}/lexemes/{lexeme.id}",
            json={
                "source_text": "слово",
                "x": 10,
                "y": 10,
                "width": 100,
                "height": 40,
                "x2": 600,
                "y2": 10,
                "width2": 90,
                "height2": 40,
            },
        )

    assert response.status_code == 200
    assert service.received is not None
    assert (
        service.received.x2,
        service.received.y2,
        service.received.width2,
        service.received.height2,
    ) == (600, 10, 90, 40)


def test_update_lexeme_rejects_a_non_positive_bounding_box() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{uuid4()}/lexemes/{uuid4()}",
            json={"source_text": "слово", "x": 0, "y": 0, "width": 0, "height": 10},
        )

    assert response.status_code == 422


def test_update_lexeme_returns_field_errors_for_invalid_bounds() -> None:
    service = StubUpdateLexemeService(
        error=LexemeValidationError({"width": "Виділена область виходить за межі."})
    )

    with client_for(update_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{uuid4()}/lexemes/{uuid4()}",
            json={"source_text": "слово", "x": 0, "y": 0, "width": 10, "height": 10},
        )

    assert response.status_code == 422
    assert "width" in response.json()["errors"]


def test_update_lexeme_not_owned_or_missing_returns_404() -> None:
    for error in (LexemeAccessError(uuid4()), LexemeNotFoundError(uuid4(), uuid4())):
        service = StubUpdateLexemeService(error=error)
        with client_for(update_service=service) as client:
            client.cookies.set("cadmus_session", "token")
            response = client.patch(
                f"/dictionaries/{uuid4()}/lexemes/{uuid4()}",
                json={
                    "source_text": "слово",
                    "x": 0,
                    "y": 0,
                    "width": 10,
                    "height": 10,
                },
            )
        assert response.status_code == 404


def test_delete_lexeme_requires_authentication() -> None:
    with client_for() as client:
        response = client.delete(f"/dictionaries/{uuid4()}/lexemes/{uuid4()}")
    assert response.status_code == 401


def test_delete_lexeme_returns_204() -> None:
    dictionary_id = uuid4()
    lexeme_id = uuid4()
    service = StubDeleteLexemeService()

    with client_for(delete_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.delete(f"/dictionaries/{dictionary_id}/lexemes/{lexeme_id}")

    assert response.status_code == 204
    assert service.deleted is not None
    assert service.deleted[0] == dictionary_id
    assert service.deleted[1] == lexeme_id


def test_delete_lexeme_not_owned_or_missing_returns_404() -> None:
    for error in (LexemeAccessError(uuid4()), LexemeNotFoundError(uuid4(), uuid4())):
        service = StubDeleteLexemeService(error=error)
        with client_for(delete_service=service) as client:
            client.cookies.set("cadmus_session", "token")
            response = client.delete(f"/dictionaries/{uuid4()}/lexemes/{uuid4()}")
        assert response.status_code == 404
