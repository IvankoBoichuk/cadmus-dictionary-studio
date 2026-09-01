"""HTTP contract for the cross-dictionary ``/review`` queue routes."""

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
from cadmus.lexicography import EntryAccessError, EntryStatus, EntryValidationError
from cadmus.review import (
    EntryNotAwaitingReviewError,
    ReviewAccessError,
    ReviewQueueItem,
    ReviewService,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

REVIEWER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
DICTIONARY_ID = uuid4()
ENTRY_ID = uuid4()
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


@dataclass
class StubAuthenticationService:
    def login(self, email: str, password: str) -> None:
        raise AssertionError("not used")

    def authenticate(self, token: str) -> User:
        if token != "token":
            raise AuthenticationError(AuthenticationFailure.INVALID_SESSION)
        return User(
            id=REVIEWER_ID,
            email="reviewer@example.com",
            password_hash="not-returned",
            status=AccountStatus.ACTIVE,
            created_at=NOW,
            activated_at=NOW,
        )

    def logout(self, token: str) -> None:
        raise AssertionError("not used")


@dataclass
class _Entry:
    id: UUID
    status: EntryStatus


@dataclass
class StubReviewService:
    queue: list[ReviewQueueItem] = field(default_factory=list)
    approve_error: Exception | None = None
    send_back_error: Exception | None = None
    calls: list[tuple[str, UUID, UUID, str | None]] = field(default_factory=list)

    def list_queue(self, actor_id: UUID) -> list[ReviewQueueItem]:
        self.calls.append(("list_queue", actor_id, actor_id, None))
        return list(self.queue)

    def approve(
        self, entry_id: UUID, actor_id: UUID, note: str | None = None
    ) -> _Entry:
        self.calls.append(("approve", entry_id, actor_id, note))
        if self.approve_error is not None:
            raise self.approve_error
        return _Entry(id=entry_id, status=EntryStatus.COMPLETE)

    def send_back(
        self, entry_id: UUID, actor_id: UUID, note: str | None = None
    ) -> _Entry:
        self.calls.append(("send_back", entry_id, actor_id, note))
        if self.send_back_error is not None:
            raise self.send_back_error
        return _Entry(id=entry_id, status=EntryStatus.DRAFT)


def _queue_item(**overrides: object) -> ReviewQueueItem:
    defaults: dict[str, object] = {
        "entry_id": ENTRY_ID,
        "dictionary_id": DICTIONARY_ID,
        "dictionary_title": "Словник",
        "headword": "слово",
        "status": EntryStatus.READY_TO_REVIEW,
        "field_count": 4,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return ReviewQueueItem(**defaults)  # type: ignore[arg-type]


def client_for(
    *,
    review_service: StubReviewService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            review_service=cast(ReviewService, review_service or StubReviewService()),
        )
    )


def test_queue_requires_authentication() -> None:
    with client_for() as client:
        response = client.get("/review/queue")
    assert response.status_code == 401


def test_queue_returns_items() -> None:
    service = StubReviewService(queue=[_queue_item()])
    with client_for(review_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get("/review/queue")
    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "entry_id": str(ENTRY_ID),
            "dictionary_id": str(DICTIONARY_ID),
            "dictionary_title": "Словник",
            "headword": "слово",
            "status": "ready_to_review",
            "field_count": 4,
            "updated_at": "2026-09-01T12:00:00Z",
        }
    ]
    assert service.calls[0][0] == "list_queue"


def test_approve_returns_new_status_and_forwards_note() -> None:
    service = StubReviewService()
    with client_for(review_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/review/entries/{ENTRY_ID}/approve", json={"note": "ок"}
        )
    assert response.status_code == 200
    assert response.json() == {"entry_id": str(ENTRY_ID), "status": "complete"}
    assert service.calls == [("approve", ENTRY_ID, REVIEWER_ID, "ок")]


def test_approve_without_body_is_allowed() -> None:
    service = StubReviewService()
    with client_for(review_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/review/entries/{ENTRY_ID}/approve")
    assert response.status_code == 200
    assert service.calls == [("approve", ENTRY_ID, REVIEWER_ID, None)]


def test_approve_on_inaccessible_entry_is_404() -> None:
    service = StubReviewService(approve_error=ReviewAccessError(DICTIONARY_ID))
    with client_for(review_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/review/entries/{ENTRY_ID}/approve")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_approve_on_unknown_entry_is_404() -> None:
    service = StubReviewService(approve_error=EntryAccessError(ENTRY_ID))
    with client_for(review_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/review/entries/{ENTRY_ID}/approve")
    assert response.status_code == 404


def test_approve_when_not_awaiting_review_is_409() -> None:
    service = StubReviewService(
        approve_error=EntryNotAwaitingReviewError(ENTRY_ID, EntryStatus.DRAFT)
    )
    with client_for(review_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/review/entries/{ENTRY_ID}/approve")
    assert response.status_code == 409
    assert response.json()["code"] == "not_awaiting_review"


def test_approve_failing_schema_is_422_with_field_errors() -> None:
    service = StubReviewService(
        approve_error=EntryValidationError({"meaning": "Відсутнє значення."})
    )
    with client_for(review_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/review/entries/{ENTRY_ID}/approve")
    assert response.status_code == 422
    assert response.json() == {"errors": {"meaning": "Відсутнє значення."}}


def test_send_back_returns_draft_status() -> None:
    service = StubReviewService()
    with client_for(review_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/review/entries/{ENTRY_ID}/send-back", json={"note": "виправте"}
        )
    assert response.status_code == 200
    assert response.json() == {"entry_id": str(ENTRY_ID), "status": "draft"}
    assert service.calls == [("send_back", ENTRY_ID, REVIEWER_ID, "виправте")]
