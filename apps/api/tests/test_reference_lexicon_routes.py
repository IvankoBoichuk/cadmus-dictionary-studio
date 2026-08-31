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
from cadmus.lexicography import (
    EntryReferenceLink,
    LinkedReferenceLemma,
    ManageEntryReferenceLinksService,
    ReferenceLemmaNotStandardError,
    ReferenceLinkOrigin,
    ReferenceLinkStatus,
    ReferenceRelationType,
)
from cadmus.reference_lexicon import (
    ReferenceLemma,
    ReferenceLemmaMatch,
    ReferenceLexicon,
    ReferenceLexiconNotFoundError,
    ReferenceLexiconQueryService,
    ReferenceMatchType,
)
from cadmus_api.routes.reference_lexicons import create_reference_lexicons_router
from fastapi import FastAPI
from fastapi.testclient import TestClient

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
LEXICON_ID = uuid4()
LEMMA_ID = uuid4()
ENTRY_ID = uuid4()
LINK_ID = uuid4()


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


def _lexicon() -> ReferenceLexicon:
    return ReferenceLexicon(
        id=LEXICON_ID,
        code="vesum",
        name="Великий електронний словник української мови",
        language_code="uk",
        version="6.7.8",
        source_url="https://github.com/brown-uk/dict_uk",
        license_id="CC-BY-NC-SA-4.0",
        source_commit="abc123",
        checksum="deadbeef",
        imported_at=NOW,
    )


def _lemma(*, standard: bool = True) -> ReferenceLemma:
    return ReferenceLemma(
        id=LEMMA_ID,
        lexicon_id=LEXICON_ID,
        external_key="господар|noun|anim,m",
        lemma="господар",
        normalized_lemma="господар",
        part_of_speech="noun",
        key_tags=["anim", "m"],
        is_standard=standard,
    )


@dataclass
class StubReferenceLexiconQueryService:
    missing: bool = False

    def get_lexicon(self, code: str) -> ReferenceLexicon:
        if self.missing or code != "vesum":
            raise ReferenceLexiconNotFoundError(code)
        return _lexicon()

    def search(
        self,
        code: str,
        query: str,
        *,
        standard_only: bool = True,
        limit: int = 20,
    ) -> list[ReferenceLemmaMatch]:
        self.get_lexicon(code)
        assert standard_only is True
        assert limit == 20
        return [
            ReferenceLemmaMatch(
                lemma=_lemma(),
                match_type=ReferenceMatchType.WORD_FORM,
                matched_form=query,
                matched_form_morphology="noun:anim:m:v_rod",
                matched_form_tags=["noun", "anim", "m", "v_rod"],
                matched_form_features={
                    "case": "v_rod",
                    "gender": "m",
                    "animacy": "anim",
                },
            )
        ]


@dataclass
class StubEntryReferenceLinksService:
    reject_non_standard: bool = False
    deleted: list[tuple[UUID, UUID, UUID]] = field(default_factory=list)

    def _linked(self) -> LinkedReferenceLemma:
        lemma = _lemma(standard=not self.reject_non_standard)
        link = EntryReferenceLink(
            id=LINK_ID,
            entry_id=ENTRY_ID,
            reference_lemma_id=LEMMA_ID,
            relation_type=ReferenceRelationType.STANDARD_EQUIVALENT,
            origin=ReferenceLinkOrigin.MANUAL,
            validation_status=ReferenceLinkStatus.CONFIRMED,
            confidence=None,
            created_at=NOW,
            created_by=OWNER_ID,
        )
        return LinkedReferenceLemma(link=link, lemma=lemma)

    def list(self, entry_id: UUID, actor_id: UUID) -> list[LinkedReferenceLemma]:
        assert entry_id == ENTRY_ID
        assert actor_id == OWNER_ID
        return [self._linked()]

    def create(
        self,
        entry_id: UUID,
        actor_id: UUID,
        reference_lemma_id: UUID,
        *,
        relation_type: ReferenceRelationType = (
            ReferenceRelationType.STANDARD_EQUIVALENT
        ),
    ) -> LinkedReferenceLemma:
        assert entry_id == ENTRY_ID
        assert actor_id == OWNER_ID
        assert reference_lemma_id == LEMMA_ID
        assert relation_type is ReferenceRelationType.STANDARD_EQUIVALENT
        if self.reject_non_standard:
            raise ReferenceLemmaNotStandardError(str(reference_lemma_id))
        return self._linked()

    def delete(self, entry_id: UUID, link_id: UUID, actor_id: UUID) -> None:
        self.deleted.append((entry_id, link_id, actor_id))


def client_for(
    *,
    query: StubReferenceLexiconQueryService | None = None,
    links: StubEntryReferenceLinksService | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_reference_lexicons_router(
            cast(AuthenticationService, StubAuthenticationService()),
            cast(
                ReferenceLexiconQueryService,
                query or StubReferenceLexiconQueryService(),
            ),
            cast(
                ManageEntryReferenceLinksService,
                links or StubEntryReferenceLinksService(),
            ),
        )
    )
    return TestClient(app)


def test_reference_search_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(
            "/reference-lexicons/vesum/lemmas",
            params={"q": "господаря"},
        )

    assert response.status_code == 401


def test_reference_search_returns_lemma_for_matching_word_form() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(
            "/reference-lexicons/vesum/lemmas",
            params={"q": "господаря"},
        )

    assert response.status_code == 200
    assert response.json()[0]["lemma"] == "господар"
    assert response.json()[0]["match_type"] == "word_form"
    assert response.json()[0]["matched_form"] == "господаря"
    assert response.json()[0]["matched_form_morphology"] == "noun:anim:m:v_rod"
    assert response.json()[0]["matched_form_features"]["case"] == "v_rod"
    assert response.json()[0]["is_standard"] is True


def test_reference_search_returns_404_when_vesum_is_not_imported() -> None:
    with client_for(query=StubReferenceLexiconQueryService(missing=True)) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(
            "/reference-lexicons/vesum/lemmas",
            params={"q": "господар"},
        )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_create_standard_equivalent_returns_confirmed_manual_link() -> None:
    with client_for() as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/entries/{ENTRY_ID}/reference-links",
            json={
                "reference_lemma_id": str(LEMMA_ID),
                "relation_type": "standard_equivalent",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["lemma"]["lemma"] == "господар"
    assert body["origin"] == "manual"
    assert body["validation_status"] == "confirmed"


def test_standard_equivalent_rejects_non_standard_reference() -> None:
    links = StubEntryReferenceLinksService(reject_non_standard=True)
    with client_for(links=links) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            f"/entries/{ENTRY_ID}/reference-links",
            json={"reference_lemma_id": str(LEMMA_ID)},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "non_standard_reference"


def test_delete_reference_link_returns_204() -> None:
    links = StubEntryReferenceLinksService()
    with client_for(links=links) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.delete(
            f"/entries/{ENTRY_ID}/reference-links/{LINK_ID}",
        )

    assert response.status_code == 204
    assert response.content == b""
    assert links.deleted == [(ENTRY_ID, LINK_ID, OWNER_ID)]


def test_reference_router_openapi_declares_empty_204_response() -> None:
    with client_for() as client:
        schema = client.app.openapi()

    operation = schema["paths"][
        "/entries/{entry_id}/reference-links/{link_id}"
    ]["delete"]
    no_content = operation["responses"]["204"]
    assert "content" not in no_content
