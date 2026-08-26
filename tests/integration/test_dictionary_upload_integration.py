"""Full dictionary draft flow against real PostgreSQL and MinIO.

Covers the AC/DoD requirement to exercise upload, storage, persistence,
metadata save/edit, duplicate detection, and cross-user isolation against
realistic boundaries rather than in-memory fakes.
"""

import os
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from cadmus.config import Settings
from cadmus.infrastructure.object_storage import create_object_storage
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.sources import (
    CompleteSourceInspectionService,
    ContributorInput,
    ContributorRole,
    DeleteDictionaryService,
    DictionaryAccessError,
    DictionaryPage,
    DuplicateSourceError,
    GetDictionaryService,
    LegalStatus,
    MetadataInput,
    ObjectNotFoundError,
    RecordPageSplitService,
    SaveDictionaryMetadataService,
    SourceInspectionQueueUnavailableError,
    UploadDictionaryService,
)
from sqlalchemy import Engine, create_engine, text

pytestmark = pytest.mark.integration

VALID_PDF = Path("fixtures/dictionaries/sample-dictionary.pdf").read_bytes()


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
        connection.execute(text("DELETE FROM cadmus.dictionary_events"))
        connection.execute(text("DELETE FROM cadmus.dictionary_pages"))
        connection.execute(text("DELETE FROM cadmus.dictionary_source_files"))
        connection.execute(text("DELETE FROM cadmus.dictionary_contributors"))
        connection.execute(text("DELETE FROM cadmus.dictionary_languages"))
        connection.execute(text("DELETE FROM cadmus.dictionaries"))
        connection.execute(text("DELETE FROM cadmus.authenticated_sessions"))
        connection.execute(text("DELETE FROM cadmus.email_verification_tokens"))
        connection.execute(text("DELETE FROM cadmus.users"))
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


def test_upload_persists_draft_and_source_in_postgres_and_minio() -> None:
    database_url = _prepare_database()
    engine = create_engine(database_url)
    owner_id = _create_user(engine, f"owner-{uuid4()}@example.com")
    settings = Settings()
    unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    object_storage = create_object_storage(settings)
    upload_service = UploadDictionaryService(
        unit_of_work_factory=unit_of_work_factory,
        object_storage=object_storage,
        inspection_queue=NoOpInspectionQueue(),
        max_upload_size_bytes=10 * 1024 * 1024,
    )
    get_service = GetDictionaryService(unit_of_work_factory)

    outcome = upload_service.upload(
        owner_id, "Словник.pdf", "application/pdf", BytesIO(VALID_PDF)
    )

    try:
        with engine.connect() as connection:
            stored_dictionary = connection.execute(
                text(
                    "SELECT owner_id, status, updated_by FROM cadmus.dictionaries "
                    "WHERE id = :id"
                ),
                {"id": outcome.dictionary.id},
            ).one()
            stored_source = connection.execute(
                text(
                    "SELECT original_filename, checksum_sha256, storage_key, "
                    "inspection_status FROM cadmus.dictionary_source_files "
                    "WHERE dictionary_id = :id"
                ),
                {"id": outcome.dictionary.id},
            ).one()
            event_types = [
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT event_type FROM cadmus.dictionary_events "
                        "WHERE dictionary_id = :id ORDER BY occurred_at"
                    ),
                    {"id": outcome.dictionary.id},
                )
            ]

        assert stored_dictionary.owner_id == owner_id
        assert stored_dictionary.status == "draft"
        assert stored_dictionary.updated_by == owner_id
        assert stored_source.original_filename == "Словник.pdf"
        assert stored_source.inspection_status == "pending"
        assert event_types == ["created", "source_uploaded"]

        downloaded = BytesIO()
        object_storage.download(stored_source.storage_key, downloaded)
        assert downloaded.getvalue() == VALID_PDF

        # A second upload of the same bytes by the same owner is a duplicate,
        # and must not create an extra dictionary or a second stored object.
        with pytest.raises(DuplicateSourceError):
            upload_service.upload(
                owner_id, "again.pdf", "application/pdf", BytesIO(VALID_PDF)
            )
        with engine.connect() as connection:
            dictionary_count = connection.execute(
                text("SELECT count(*) FROM cadmus.dictionaries WHERE owner_id = :id"),
                {"id": owner_id},
            ).scalar_one()
        assert dictionary_count == 1

        # A different owner uploading the same content is not a duplicate.
        other_owner_id = _create_user(engine, f"other-{uuid4()}@example.com")
        other_outcome = upload_service.upload(
            other_owner_id, "same-content.pdf", "application/pdf", BytesIO(VALID_PDF)
        )
        assert other_outcome.dictionary.id != outcome.dictionary.id

        # An unauthorized user cannot read the first owner's dictionary.
        with pytest.raises(DictionaryAccessError):
            get_service.get(outcome.dictionary.id, other_owner_id)

        other_storage_key = get_service.get_source_file(
            other_outcome.dictionary.id, other_owner_id
        ).storage_key
        object_storage.delete(other_storage_key)
    finally:
        object_storage.delete(outcome.source_file.storage_key)
        engine.dispose()


def test_metadata_can_be_saved_and_edited_without_reuploading_the_source() -> None:
    database_url = _prepare_database()
    engine = create_engine(database_url)
    owner_id = _create_user(engine, f"owner-{uuid4()}@example.com")
    settings = Settings()
    unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    object_storage = create_object_storage(settings)
    upload_service = UploadDictionaryService(
        unit_of_work_factory=unit_of_work_factory,
        object_storage=object_storage,
        inspection_queue=NoOpInspectionQueue(),
        max_upload_size_bytes=10 * 1024 * 1024,
    )
    metadata_service = SaveDictionaryMetadataService(unit_of_work_factory)
    get_service = GetDictionaryService(unit_of_work_factory)

    outcome = upload_service.upload(
        owner_id, "Словник.pdf", "application/pdf", BytesIO(VALID_PDF)
    )
    dictionary_id = outcome.dictionary.id

    try:
        first_save = metadata_service.save(
            dictionary_id,
            owner_id,
            MetadataInput(
                title="Словник української мови",
                description=None,
                article_description=None,
                dictionary_type=None,
                publisher=None,
                publication_year=1993,
                edition=None,
                isbn="0-306-40615-2",
                digital_source=None,
                legal_status=LegalStatus.PUBLIC_DOMAIN,
                license_type=None,
                permission_reference=None,
                rights_note=None,
                contributors=(
                    ContributorInput(
                        name="Борис Грінченко", role=ContributorRole.COMPILER
                    ),
                ),
                language_codes=("uk",),
            ),
        )
        assert first_save.missing_required_fields == []
        assert first_save.dictionary.isbn == "0306406152"

        # Editing must not require or affect the stored source file.
        source_before = get_service.get_source_file(dictionary_id, owner_id)
        second_save = metadata_service.save(
            dictionary_id,
            owner_id,
            MetadataInput(
                title="Словник української мови, друге видання",
                description="Оновлений опис.",
                article_description=None,
                dictionary_type=None,
                publisher=None,
                publication_year=1993,
                edition="2",
                isbn="0-306-40615-2",
                digital_source=None,
                legal_status=LegalStatus.PUBLIC_DOMAIN,
                license_type=None,
                permission_reference=None,
                rights_note=None,
                contributors=(
                    ContributorInput(
                        name="Борис Грінченко", role=ContributorRole.COMPILER
                    ),
                    ContributorInput(name="Марія Загірня", role=ContributorRole.AUTHOR),
                ),
                language_codes=("uk",),
            ),
        )
        source_after = get_service.get_source_file(dictionary_id, owner_id)

        assert second_save.dictionary.title is not None
        assert second_save.dictionary.title.endswith("друге видання")
        assert second_save.dictionary.updated_at >= first_save.dictionary.updated_at
        assert source_after.storage_key == source_before.storage_key
        assert source_after.checksum_sha256 == source_before.checksum_sha256

        with engine.connect() as connection:
            contributor_names = [
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT name FROM cadmus.dictionary_contributors "
                        "WHERE dictionary_id = :id ORDER BY position"
                    ),
                    {"id": dictionary_id},
                )
            ]
            metadata_events = connection.execute(
                text(
                    "SELECT count(*) FROM cadmus.dictionary_events "
                    "WHERE dictionary_id = :id AND event_type = 'metadata_updated'"
                ),
                {"id": dictionary_id},
            ).scalar_one()
        assert contributor_names == ["Борис Грінченко", "Марія Загірня"]
        assert metadata_events == 2
    finally:
        object_storage.delete(outcome.source_file.storage_key)
        engine.dispose()


def test_page_split_persists_pages_and_tracks_the_backfill_queue() -> None:
    database_url = _prepare_database()
    engine = create_engine(database_url)
    owner_id = _create_user(engine, f"owner-{uuid4()}@example.com")
    settings = Settings()
    unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    object_storage = create_object_storage(settings)
    upload_service = UploadDictionaryService(
        unit_of_work_factory=unit_of_work_factory,
        object_storage=object_storage,
        inspection_queue=NoOpInspectionQueue(),
        max_upload_size_bytes=10 * 1024 * 1024,
    )
    inspection_service = CompleteSourceInspectionService(unit_of_work_factory)
    split_service = RecordPageSplitService(unit_of_work_factory)

    outcome = upload_service.upload(
        owner_id, "Словник.pdf", "application/pdf", BytesIO(VALID_PDF)
    )
    source_file_id = outcome.source_file.id

    try:
        # Not yet inspected: not a page-split candidate.
        with unit_of_work_factory() as unit_of_work:
            pending = unit_of_work.sources.list_source_files_pending_page_split()
        assert source_file_id not in {source_file.id for source_file in pending}

        inspection_service.complete(source_file_id, page_count=2)

        with unit_of_work_factory() as unit_of_work:
            pending = unit_of_work.sources.list_source_files_pending_page_split()
        assert source_file_id in {source_file.id for source_file in pending}

        pages = [
            DictionaryPage(
                id=uuid4(),
                source_file_id=source_file_id,
                page_index=index,
                processed_asset_key=f"sources/{source_file_id}/pages/{index:05d}.png",
                width=200,
                height=400,
                checksum_sha256="b" * 64,
                created_at=outcome.dictionary.created_at,
            )
            for index in range(2)
        ]
        split_service.record_success(source_file_id, pages)

        with engine.connect() as connection:
            stored_pages = connection.execute(
                text(
                    "SELECT page_index, width, height FROM cadmus.dictionary_pages "
                    "WHERE source_file_id = :id ORDER BY page_index"
                ),
                {"id": source_file_id},
            ).all()
            pages_status = connection.execute(
                text(
                    "SELECT pages_status FROM cadmus.dictionary_source_files "
                    "WHERE id = :id"
                ),
                {"id": source_file_id},
            ).scalar_one()
        assert [row.page_index for row in stored_pages] == [0, 1]
        assert pages_status == "completed"

        with unit_of_work_factory() as unit_of_work:
            pending = unit_of_work.sources.list_source_files_pending_page_split()
        assert source_file_id not in {source_file.id for source_file in pending}

        # A later failed re-split makes it a backfill candidate again, and
        # replaces the previously stored pages.
        split_service.record_failure(source_file_id, "boom")

        with engine.connect() as connection:
            remaining_page_count = connection.execute(
                text(
                    "SELECT count(*) FROM cadmus.dictionary_pages "
                    "WHERE source_file_id = :id"
                ),
                {"id": source_file_id},
            ).scalar_one()
        assert remaining_page_count == 2

        with unit_of_work_factory() as unit_of_work:
            pending = unit_of_work.sources.list_source_files_pending_page_split()
        assert source_file_id in {source_file.id for source_file in pending}
    finally:
        object_storage.delete(outcome.source_file.storage_key)
        engine.dispose()


def test_list_and_delete_remove_the_dictionary_and_all_its_stored_objects() -> None:
    database_url = _prepare_database()
    engine = create_engine(database_url)
    owner_id = _create_user(engine, f"owner-{uuid4()}@example.com")
    settings = Settings()
    unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    object_storage = create_object_storage(settings)
    upload_service = UploadDictionaryService(
        unit_of_work_factory=unit_of_work_factory,
        object_storage=object_storage,
        inspection_queue=NoOpInspectionQueue(),
        max_upload_size_bytes=10 * 1024 * 1024,
    )
    inspection_service = CompleteSourceInspectionService(unit_of_work_factory)
    split_service = RecordPageSplitService(unit_of_work_factory)
    get_service = GetDictionaryService(unit_of_work_factory)
    delete_service = DeleteDictionaryService(unit_of_work_factory, object_storage)

    outcome = upload_service.upload(
        owner_id, "Словник.pdf", "application/pdf", BytesIO(VALID_PDF)
    )
    dictionary_id = outcome.dictionary.id
    source_file_id = outcome.source_file.id
    inspection_service.complete(source_file_id, page_count=2)

    page_keys = [f"sources/{dictionary_id}/pages/{index:05d}.png" for index in range(2)]
    for key in page_keys:
        object_storage.upload(
            key, BytesIO(b"\x89PNG\r\n\x1a\nfixture"), 15, "image/png"
        )
    pages = [
        DictionaryPage(
            id=uuid4(),
            source_file_id=source_file_id,
            page_index=index,
            processed_asset_key=key,
            width=200,
            height=400,
            checksum_sha256="b" * 64,
            created_at=outcome.dictionary.created_at,
        )
        for index, key in enumerate(page_keys)
    ]
    split_service.record_success(source_file_id, pages)

    entries = get_service.list_for_owner(owner_id)
    assert dictionary_id in {entry.dictionary.id for entry in entries}

    delete_service.delete(dictionary_id, owner_id)

    with pytest.raises(DictionaryAccessError):
        get_service.get(dictionary_id, owner_id)
    entries_after_delete = get_service.list_for_owner(owner_id)
    assert dictionary_id not in {entry.dictionary.id for entry in entries_after_delete}

    with engine.connect() as connection:
        remaining_pages = connection.execute(
            text(
                "SELECT count(*) FROM cadmus.dictionary_pages "
                "WHERE source_file_id = :id"
            ),
            {"id": source_file_id},
        ).scalar_one()
        remaining_source_files = connection.execute(
            text("SELECT count(*) FROM cadmus.dictionary_source_files WHERE id = :id"),
            {"id": source_file_id},
        ).scalar_one()
    assert remaining_pages == 0
    assert remaining_source_files == 0

    with pytest.raises(ObjectNotFoundError):
        object_storage.download(outcome.source_file.storage_key, BytesIO())
    for key in page_keys:
        with pytest.raises(ObjectNotFoundError):
            object_storage.download(key, BytesIO())

    engine.dispose()
