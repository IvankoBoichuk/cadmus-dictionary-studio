from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.sources import (
    Contributor,
    ContributorRole,
    DeleteDictionaryService,
    Dictionary,
    DictionaryAccessError,
    DictionaryLanguage,
    DictionaryListEntry,
    DictionaryNotReadyError,
    DictionaryPage,
    DictionaryPageRange,
    DictionaryReadinessService,
    DictionaryStatus,
    DuplicateSourceError,
    GetDictionaryService,
    InspectionStatus,
    InvalidUploadError,
    LegalStatus,
    MetadataSaveOutcome,
    MetadataValidationError,
    ObjectNotFoundError,
    ObjectStorage,
    ReadinessBlocker,
    SaveDictionaryMetadataService,
    SourceFile,
    UploadDictionaryService,
    UploadOutcome,
    UploadTooLargeError,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


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


def _source_file(dictionary_id: UUID) -> SourceFile:
    return SourceFile(
        id=uuid4(),
        dictionary_id=dictionary_id,
        original_filename="dictionary.pdf",
        mime_type="application/pdf",
        byte_size=1024,
        checksum_sha256="a" * 64,
        storage_key="sources/owner/key.pdf",
        uploaded_at=NOW,
        uploaded_by=OWNER_ID,
        inspection_status=InspectionStatus.PENDING,
    )


@dataclass
class StubUploadDictionaryService:
    outcome: UploadOutcome | None = None
    error: Exception | None = None

    def upload(
        self, owner_id: UUID, filename: str, content_type: str, file: object
    ) -> UploadOutcome:
        if self.error is not None:
            raise self.error
        assert self.outcome is not None
        return self.outcome


@dataclass
class StubSaveDictionaryMetadataService:
    outcome: MetadataSaveOutcome | None = None
    error: Exception | None = None

    def save(
        self, dictionary_id: UUID, actor_id: UUID, data: object
    ) -> MetadataSaveOutcome:
        if self.error is not None:
            raise self.error
        assert self.outcome is not None
        return self.outcome


def _page_range(dictionary_id: UUID) -> DictionaryPageRange:
    return DictionaryPageRange(
        id=uuid4(), dictionary_id=dictionary_id, start_page=1, end_page=3, position=0
    )


def _page(source_file_id: UUID, page_index: int = 0) -> DictionaryPage:
    return DictionaryPage(
        id=uuid4(),
        source_file_id=source_file_id,
        page_index=page_index,
        processed_asset_key=f"sources/{source_file_id}/pages/{page_index:05d}.png",
        width=200,
        height=400,
        checksum_sha256="b" * 64,
        created_at=NOW,
    )


@dataclass
class StubGetDictionaryService:
    dictionary: Dictionary | None = None
    source_file: SourceFile | None = None
    access_error: DictionaryAccessError | None = None
    entries: list[DictionaryListEntry] | None = None
    first_page: DictionaryPage | None = None
    page_ranges: list[DictionaryPageRange] = field(default_factory=list)

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
        return self.page_ranges

    def list_for_owner(self, owner_id: UUID) -> list[DictionaryListEntry]:
        return self.entries or []

    def list_for_actor(self, actor_id: UUID) -> list[DictionaryListEntry]:
        return self.entries or []

    def get_first_page(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> DictionaryPage | None:
        if self.access_error is not None:
            raise self.access_error
        return self.first_page


@dataclass
class StubDeleteDictionaryService:
    error: DictionaryAccessError | None = None
    deleted: list[UUID] = field(default_factory=list)

    def delete(self, dictionary_id: UUID, actor_id: UUID) -> None:
        if self.error is not None:
            raise self.error
        self.deleted.append(dictionary_id)


@dataclass
class StubDictionaryReadinessService:
    dictionary: Dictionary | None = None
    error: Exception | None = None

    def confirm_configured(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        if self.error is not None:
            raise self.error
        assert self.dictionary is not None
        return self.dictionary


class StubObjectStorage:
    def __init__(self, content: bytes = b"%PDF-1.4\nfixture") -> None:
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
    upload_service: StubUploadDictionaryService | None = None,
    metadata_service: StubSaveDictionaryMetadataService | None = None,
    get_service: StubGetDictionaryService | None = None,
    object_storage: StubObjectStorage | None = None,
    authentication: StubAuthenticationService | None = None,
    delete_service: StubDeleteDictionaryService | None = None,
    readiness_service: StubDictionaryReadinessService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            upload_dictionary_service=cast(
                UploadDictionaryService,
                upload_service or StubUploadDictionaryService(),
            ),
            save_dictionary_metadata_service=cast(
                SaveDictionaryMetadataService,
                metadata_service or StubSaveDictionaryMetadataService(),
            ),
            get_dictionary_service=cast(
                GetDictionaryService, get_service or StubGetDictionaryService()
            ),
            object_storage=cast(ObjectStorage, object_storage or StubObjectStorage()),
            delete_dictionary_service=cast(
                DeleteDictionaryService,
                delete_service or StubDeleteDictionaryService(),
            ),
            dictionary_readiness_service=cast(
                DictionaryReadinessService,
                readiness_service or StubDictionaryReadinessService(),
            ),
        )
    )


def test_upload_requires_authentication() -> None:
    with client_for() as client:
        response = client.post(
            "/dictionaries/upload",
            files={"file": ("dictionary.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert response.status_code == 401


def test_upload_returns_the_new_draft() -> None:
    dictionary = _dictionary()
    source_file = _source_file(dictionary.id)
    service = StubUploadDictionaryService(
        outcome=UploadOutcome(
            dictionary=dictionary,
            source_file=source_file,
            missing_required_fields=["title", "languages", "legal_status"],
        )
    )

    with client_for(upload_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            "/dictionaries/upload",
            files={"file": ("dictionary.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["id"] == str(dictionary.id)
    assert body["status"] == "draft"
    assert body["source"]["original_filename"] == "dictionary.pdf"
    assert body["source"]["inspection_status"] == "pending"
    assert body["missing_required_fields"] == ["title", "languages", "legal_status"]


def test_upload_returns_field_errors_for_invalid_file() -> None:
    service = StubUploadDictionaryService(
        error=InvalidUploadError("file", "Файл повинен мати розширення .pdf.")
    )

    with client_for(upload_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            "/dictionaries/upload",
            files={"file": ("dictionary.txt", b"not a pdf", "text/plain")},
        )

    assert response.status_code == 422
    assert response.json()["errors"]["file"]


def test_upload_returns_duplicate_conflict_without_leaking_other_users() -> None:
    existing_id = uuid4()
    service = StubUploadDictionaryService(
        error=DuplicateSourceError(existing_id, "Наявний словник")
    )

    with client_for(upload_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            "/dictionaries/upload",
            files={"file": ("dictionary.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["dictionary_id"] == str(existing_id)
    assert body["title"] == "Наявний словник"


def test_upload_returns_413_when_too_large() -> None:
    service = StubUploadDictionaryService(error=UploadTooLargeError(100))

    with client_for(upload_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(
            "/dictionaries/upload",
            files={"file": ("dictionary.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert response.status_code == 413


def test_get_dictionary_returns_full_draft() -> None:
    dictionary = _dictionary(
        title="Словник",
        legal_status=LegalStatus.PUBLIC_DOMAIN,
    )
    dictionary.contributors = [
        Contributor(
            id=uuid4(),
            dictionary_id=dictionary.id,
            name="Автор",
            role=ContributorRole.AUTHOR,
            position=0,
        )
    ]
    dictionary.languages = [
        DictionaryLanguage(
            id=uuid4(), dictionary_id=dictionary.id, language_code="uk", position=0
        )
    ]
    service = StubGetDictionaryService(
        dictionary=dictionary,
        source_file=_source_file(dictionary.id),
        page_ranges=[_page_range(dictionary.id)],
    )

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{dictionary.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Словник"
    assert body["language_codes"] == ["uk"]
    assert body["contributors"][0]["name"] == "Автор"
    assert body["missing_required_fields"] == []
    assert [b["code"] for b in body["readiness_blockers"]] == ["source_not_verified"]


def test_get_dictionary_not_owned_returns_404_not_403() -> None:
    service = StubGetDictionaryService(access_error=DictionaryAccessError(uuid4()))

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}")

    assert response.status_code == 404


def test_save_metadata_returns_updated_draft() -> None:
    dictionary = _dictionary(title="Оновлена назва", legal_status=LegalStatus.UNKNOWN)
    service = StubSaveDictionaryMetadataService(
        outcome=MetadataSaveOutcome(
            dictionary=dictionary, missing_required_fields=["languages"]
        )
    )

    with client_for(metadata_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{dictionary.id}",
            json={
                "title": "Оновлена назва",
                "legal_status": "unknown",
                "contributors": [],
                "language_codes": [],
            },
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Оновлена назва"
    assert response.json()["missing_required_fields"] == ["languages"]


def test_save_metadata_returns_field_errors() -> None:
    service = StubSaveDictionaryMetadataService(
        error=MetadataValidationError({"isbn": "Некоректна контрольна сума ISBN-10."})
    )

    with client_for(metadata_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{uuid4()}",
            json={"isbn": "0306406153", "contributors": [], "language_codes": []},
        )

    assert response.status_code == 422
    assert "isbn" in response.json()["errors"]


def test_save_metadata_not_owned_returns_404() -> None:
    service = StubSaveDictionaryMetadataService(error=DictionaryAccessError(uuid4()))

    with client_for(metadata_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.patch(
            f"/dictionaries/{uuid4()}",
            json={"contributors": [], "language_codes": []},
        )

    assert response.status_code == 404


def test_download_source_streams_the_original_file() -> None:
    dictionary_id = uuid4()
    source_file = _source_file(dictionary_id)
    service = StubGetDictionaryService(source_file=source_file)

    with client_for(
        get_service=service, object_storage=StubObjectStorage(b"%PDF-1.4\nfixture body")
    ) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{dictionary_id}/source/download")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4\nfixture body"
    assert "dictionary.pdf" in response.headers["content-disposition"]


def test_download_source_not_owned_returns_404() -> None:
    service = StubGetDictionaryService(access_error=DictionaryAccessError(uuid4()))

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/source/download")

    assert response.status_code == 404


def test_download_source_missing_object_returns_404() -> None:
    class MissingObjectStorage(StubObjectStorage):
        def download(self, key: str, destination: object) -> None:
            raise ObjectNotFoundError(key)

    service = StubGetDictionaryService(source_file=_source_file(uuid4()))

    with client_for(
        get_service=service, object_storage=MissingObjectStorage()
    ) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/source/download")

    assert response.status_code == 404


def test_list_dictionaries_requires_authentication() -> None:
    with client_for() as client:
        response = client.get("/dictionaries")
    assert response.status_code == 401


def test_list_dictionaries_returns_the_callers_drafts() -> None:
    dictionary = _dictionary(title="Словник")
    service = StubGetDictionaryService(
        entries=[
            DictionaryListEntry(
                dictionary=dictionary,
                source_file=_source_file(dictionary.id),
                page_ranges=[],
            )
        ]
    )

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get("/dictionaries")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(dictionary.id)
    assert body[0]["source"]["pages_status"] == "pending"


def test_delete_dictionary_returns_no_content() -> None:
    dictionary_id = uuid4()
    service = StubDeleteDictionaryService()

    with client_for(delete_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.delete(f"/dictionaries/{dictionary_id}")

    assert response.status_code == 204
    assert service.deleted == [dictionary_id]


def test_delete_dictionary_not_owned_returns_404() -> None:
    service = StubDeleteDictionaryService(error=DictionaryAccessError(uuid4()))

    with client_for(delete_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.delete(f"/dictionaries/{uuid4()}")

    assert response.status_code == 404


def test_delete_dictionary_requires_authentication() -> None:
    with client_for() as client:
        response = client.delete(f"/dictionaries/{uuid4()}")
    assert response.status_code == 401


def test_thumbnail_streams_the_first_page_image() -> None:
    dictionary_id = uuid4()
    page = _page(uuid4())
    service = StubGetDictionaryService(first_page=page)

    with client_for(
        get_service=service, object_storage=StubObjectStorage(b"\x89PNG\r\n\x1a\nrest")
    ) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{dictionary_id}/thumbnail")

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n\x1a\nrest"
    assert response.headers["content-type"] == "image/png"


def test_thumbnail_missing_page_returns_404() -> None:
    service = StubGetDictionaryService(first_page=None)

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/thumbnail")

    assert response.status_code == 404


def test_thumbnail_not_owned_returns_404() -> None:
    service = StubGetDictionaryService(access_error=DictionaryAccessError(uuid4()))

    with client_for(get_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/thumbnail")

    assert response.status_code == 404


def test_configure_dictionary_returns_the_configured_draft() -> None:
    dictionary = _dictionary(
        title="Словник",
        legal_status=LegalStatus.PUBLIC_DOMAIN,
        status=DictionaryStatus.CONFIGURED,
    )
    dictionary.languages = [
        DictionaryLanguage(
            id=uuid4(), dictionary_id=dictionary.id, language_code="uk", position=0
        )
    ]
    source_file = _source_file(dictionary.id)
    source_file.inspection_status = InspectionStatus.VERIFIED
    service = StubDictionaryReadinessService(dictionary=dictionary)
    get_service = StubGetDictionaryService(
        dictionary=dictionary,
        source_file=source_file,
        page_ranges=[_page_range(dictionary.id)],
    )

    with client_for(readiness_service=service, get_service=get_service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{dictionary.id}/configure")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "configured"
    assert body["readiness_blockers"] == []


def test_configure_dictionary_rejects_when_not_ready() -> None:
    service = StubDictionaryReadinessService(
        error=DictionaryNotReadyError(
            [ReadinessBlocker(code="title", message="Вкажіть назву словника.")]
        )
    )

    with client_for(readiness_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/configure")

    assert response.status_code == 422
    body = response.json()
    assert body["blockers"] == [{"code": "title", "message": "Вкажіть назву словника."}]


def test_configure_dictionary_not_owned_returns_404() -> None:
    service = StubDictionaryReadinessService(error=DictionaryAccessError(uuid4()))

    with client_for(readiness_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/configure")

    assert response.status_code == 404


def test_configure_dictionary_requires_authentication() -> None:
    with client_for() as client:
        response = client.post(f"/dictionaries/{uuid4()}/configure")

    assert response.status_code == 401
