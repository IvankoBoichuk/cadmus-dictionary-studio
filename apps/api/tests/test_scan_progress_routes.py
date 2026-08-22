"""BH-57: HTTP adapter tests for the dictionary scan-progress route."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.lexicography import (
    LexemeAccessError,
    PageProgress,
    ScanProgress,
    ScanProgressService,
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


@dataclass
class StubScanProgressService:
    progress: ScanProgress | None = None
    error: Exception | None = None

    def get_progress(self, dictionary_id: UUID, actor_id: UUID) -> ScanProgress:
        if self.error is not None:
            raise self.error
        assert self.progress is not None
        return self.progress


def client_for(
    scan_progress_service: StubScanProgressService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            scan_progress_service=cast(
                ScanProgressService, scan_progress_service or StubScanProgressService()
            ),
        )
    )


def test_get_scan_progress_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(f"/dictionaries/{uuid4()}/scan-progress")
    assert response.status_code == 401


def test_get_scan_progress_returns_aggregate_and_per_page_status() -> None:
    progress = ScanProgress(
        total_pages=3,
        processed_pages=2,
        pages=(
            PageProgress(page_number=1, has_lexemes=True),
            PageProgress(page_number=2, has_lexemes=False),
            PageProgress(page_number=3, has_lexemes=True),
        ),
    )
    service = StubScanProgressService(progress=progress)

    with client_for(scan_progress_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/scan-progress")

    assert response.status_code == 200
    body = response.json()
    assert body["total_pages"] == 3
    assert body["processed_pages"] == 2
    assert body["pages"] == [
        {"page_number": 1, "has_lexemes": True},
        {"page_number": 2, "has_lexemes": False},
        {"page_number": 3, "has_lexemes": True},
    ]


def test_get_scan_progress_not_owned_returns_404() -> None:
    service = StubScanProgressService(error=LexemeAccessError(uuid4()))

    with client_for(scan_progress_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/scan-progress")

    assert response.status_code == 404
