"""FastAPI application composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from cadmus.access import AuthorizationService, ListMembersService, ManageMembersService
from cadmus.config import Settings
from cadmus.geography import GeographyQueryService
from cadmus.identity import (
    AccountService,
    AuthenticationService,
    GoogleAuthenticationService,
    PasswordResetService,
    RegistrationService,
)
from cadmus.infrastructure.access import create_access_unit_of_work_factory
from cadmus.infrastructure.ai_schema import (
    CeleryArticleSchemaQueue,
    CeleryEntryExtractionQueue,
)
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.email import SmtpEmailSender
from cadmus.infrastructure.entry_render import Jinja2EntryPresentationRenderer
from cadmus.infrastructure.geography import create_geography_unit_of_work_factory
from cadmus.infrastructure.google_oauth import AuthlibGoogleOAuthClient
from cadmus.infrastructure.identity import create_identity_unit_of_work_factory
from cadmus.infrastructure.lexicography import create_lexicography_unit_of_work_factory
from cadmus.infrastructure.object_storage import create_object_storage
from cadmus.infrastructure.ocr import (
    CeleryDictionaryScanQueue,
    CeleryOcrSuggestionQueue,
)
from cadmus.infrastructure.processing import (
    create_processing_unit_of_work_factory,
)
from cadmus.infrastructure.reference_lexicon import (
    create_reference_lexicon_unit_of_work_factory,
)
from cadmus.infrastructure.reference_links import (
    create_entry_reference_link_unit_of_work_factory,
)
from cadmus.infrastructure.review import create_review_unit_of_work_factory
from cadmus.infrastructure.security import (
    ScryptPasswordHasher,
    SecurePasswordResetTokenProvider,
    SecureSessionTokenProvider,
    SecureVerificationTokenProvider,
)
from cadmus.infrastructure.source_inspection_queue import CeleryInspectionQueue
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.infrastructure.task_queue import CeleryTaskQueue, create_celery_client
from cadmus.lexicography import (
    ActivateArticleSchemaService,
    CreateEntryFieldService,
    CreateLexemeService,
    DeleteEntryFieldService,
    DeleteLexemeService,
    EntryQueryService,
    FinishScanningService,
    LexemeQueryService,
    ManageEntryReferenceLinksService,
    PromoteLexemeToEntryService,
    QueueArticleSchemaGenerationService,
    QueueDictionaryScanService,
    QueueEntryFieldExtractionService,
    RenderEntryService,
    SaveArticleSchemaService,
    ScanProgressService,
    SuggestLexemesService,
    UpdateEntryFieldService,
    UpdateLexemeService,
    ValidateEntryService,
)
from cadmus.processing import (
    ProcessingTaskKind,
    ProcessingTaskService,
    TaskQueue,
)
from cadmus.reference_lexicon import ReferenceLexiconQueryService
from cadmus.review import ReviewService
from cadmus.sources import (
    AbbreviationCrudService,
    AbbreviationImportService,
    AdvanceDictionaryProcessingStatusService,
    DeleteDictionaryService,
    DictionaryReadinessService,
    GetDictionaryService,
    MarkDictionaryScannedService,
    ObjectStorage,
    PublishDictionaryService,
    SaveDictionaryMetadataService,
    SavePageRangesService,
    SettlementConfirmationService,
    SettlementMappingCrudService,
    SettlementMappingImportService,
    SettlementSearchService,
    UploadDictionaryService,
)
from fastapi import FastAPI
from sqlalchemy import Engine, text

from cadmus_api.routes.abbreviations import create_abbreviations_router
from cadmus_api.routes.article_schemas import create_article_schemas_router
from cadmus_api.routes.auth import create_auth_router
from cadmus_api.routes.dictionaries import create_dictionaries_router
from cadmus_api.routes.entries import create_entries_router
from cadmus_api.routes.finish_scanning import create_finish_scanning_router
from cadmus_api.routes.geography import create_geography_router
from cadmus_api.routes.google_oauth import create_google_oauth_router
from cadmus_api.routes.health import create_health_router
from cadmus_api.routes.lexemes import (
    create_lexeme_management_router,
    create_lexemes_router,
)
from cadmus_api.routes.ocr_scan import create_ocr_scan_router
from cadmus_api.routes.ocr_suggestions import create_ocr_suggestions_router
from cadmus_api.routes.page_ranges import create_page_ranges_router
from cadmus_api.routes.pages import create_pages_router
from cadmus_api.routes.processing_tasks import create_processing_tasks_router
from cadmus_api.routes.project_members import create_project_members_router
from cadmus_api.routes.publish_dictionary import create_publish_dictionary_router
from cadmus_api.routes.reference_lexicons import create_reference_lexicons_router
from cadmus_api.routes.review import create_review_router
from cadmus_api.routes.scan_progress import create_scan_progress_router
from cadmus_api.routes.settlements import create_settlements_router
from cadmus_api.routes.tasks import create_tasks_router


def create_app(
    settings: Settings | None = None,
    database_engine: Engine | None = None,
    task_queue: TaskQueue | None = None,
    processing_task_service: ProcessingTaskService | None = None,
    object_storage: ObjectStorage | None = None,
    registration_service: RegistrationService | None = None,
    authentication_service: AuthenticationService | None = None,
    google_authentication_service: GoogleAuthenticationService | None = None,
    password_reset_service: PasswordResetService | None = None,
    account_service: AccountService | None = None,
    upload_dictionary_service: UploadDictionaryService | None = None,
    save_dictionary_metadata_service: SaveDictionaryMetadataService | None = None,
    get_dictionary_service: GetDictionaryService | None = None,
    delete_dictionary_service: DeleteDictionaryService | None = None,
    dictionary_readiness_service: DictionaryReadinessService | None = None,
    save_page_ranges_service: SavePageRangesService | None = None,
    abbreviation_crud_service: AbbreviationCrudService | None = None,
    abbreviation_import_service: AbbreviationImportService | None = None,
    geography_query_service: GeographyQueryService | None = None,
    settlement_mapping_crud_service: SettlementMappingCrudService | None = None,
    settlement_search_service: SettlementSearchService | None = None,
    settlement_confirmation_service: SettlementConfirmationService | None = None,
    settlement_mapping_import_service: SettlementMappingImportService | None = None,
    create_lexeme_service: CreateLexemeService | None = None,
    lexeme_query_service: LexemeQueryService | None = None,
    update_lexeme_service: UpdateLexemeService | None = None,
    delete_lexeme_service: DeleteLexemeService | None = None,
    scan_progress_service: ScanProgressService | None = None,
    mark_dictionary_scanned_service: MarkDictionaryScannedService | None = None,
    advance_dictionary_processing_status_service: (
        AdvanceDictionaryProcessingStatusService | None
    ) = None,
    publish_dictionary_service: PublishDictionaryService | None = None,
    finish_scanning_service: FinishScanningService | None = None,
    suggest_lexemes_service: SuggestLexemesService | None = None,
    queue_dictionary_scan_service: QueueDictionaryScanService | None = None,
    queue_article_schema_generation_service: (
        QueueArticleSchemaGenerationService | None
    ) = None,
    activate_article_schema_service: ActivateArticleSchemaService | None = None,
    save_article_schema_service: SaveArticleSchemaService | None = None,
    promote_lexeme_to_entry_service: PromoteLexemeToEntryService | None = None,
    queue_entry_field_extraction_service: QueueEntryFieldExtractionService
    | None = None,
    create_entry_field_service: CreateEntryFieldService | None = None,
    update_entry_field_service: UpdateEntryFieldService | None = None,
    delete_entry_field_service: DeleteEntryFieldService | None = None,
    validate_entry_service: ValidateEntryService | None = None,
    render_entry_service: RenderEntryService | None = None,
    entry_query_service: EntryQueryService | None = None,
    reference_lexicon_query_service: ReferenceLexiconQueryService | None = None,
    manage_entry_reference_links_service: (
        ManageEntryReferenceLinksService | None
    ) = None,
    authorization_service: AuthorizationService | None = None,
    manage_members_service: ManageMembersService | None = None,
    list_members_service: ListMembersService | None = None,
    review_service: ReviewService | None = None,
) -> FastAPI:
    """Create an API whose lifespan verifies and owns its database connection."""
    app_settings = settings if settings is not None else Settings()
    engine = database_engine or create_database_engine(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        app.state.database_engine = engine
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title=app_settings.name,
        version=app_settings.version,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.task_queue = (
        task_queue
        if task_queue is not None
        else CeleryTaskQueue(create_celery_client(app_settings))
    )
    app.state.object_storage = (
        object_storage
        if object_storage is not None
        else create_object_storage(app_settings)
    )
    unit_of_work_factory = create_identity_unit_of_work_factory(engine)
    password_hasher = ScryptPasswordHasher()
    app.state.registration_service = (
        registration_service
        if registration_service is not None
        else RegistrationService(
            unit_of_work_factory=unit_of_work_factory,
            password_hasher=password_hasher,
            token_provider=SecureVerificationTokenProvider(),
            email_sender=SmtpEmailSender(app_settings),
            public_web_url=app_settings.public_web_url,
            token_lifetime=timedelta(
                hours=app_settings.verification_token_lifetime_hours
            ),
        )
    )
    app.state.authentication_service = (
        authentication_service
        if authentication_service is not None
        else AuthenticationService(
            unit_of_work_factory=unit_of_work_factory,
            password_hasher=password_hasher,
            session_token_provider=SecureSessionTokenProvider(),
            session_lifetime=timedelta(hours=app_settings.session_lifetime_hours),
        )
    )
    app.state.google_authentication_service = google_authentication_service
    if app.state.google_authentication_service is None and (
        app_settings.google_oauth_client_id is not None
        and app_settings.google_oauth_client_secret is not None
        and app_settings.google_oauth_redirect_url is not None
    ):
        app.state.google_authentication_service = GoogleAuthenticationService(
            unit_of_work_factory=unit_of_work_factory,
            google_oauth_client=AuthlibGoogleOAuthClient(
                client_id=app_settings.google_oauth_client_id,
                client_secret=app_settings.google_oauth_client_secret.get_secret_value(),
                redirect_url=app_settings.google_oauth_redirect_url,
                timeout_seconds=app_settings.google_oauth_timeout_seconds,
            ),
            authentication_service=app.state.authentication_service,
        )
    app.state.password_reset_service = (
        password_reset_service
        if password_reset_service is not None
        else PasswordResetService(
            unit_of_work_factory=unit_of_work_factory,
            password_hasher=password_hasher,
            token_provider=SecurePasswordResetTokenProvider(),
            email_sender=SmtpEmailSender(app_settings),
            public_web_url=app_settings.public_web_url,
            token_lifetime=timedelta(
                hours=app_settings.password_reset_token_lifetime_hours
            ),
        )
    )
    app.state.account_service = (
        account_service
        if account_service is not None
        else AccountService(
            unit_of_work_factory=unit_of_work_factory,
            password_hasher=password_hasher,
            session_token_provider=SecureSessionTokenProvider(),
            email_change_token_provider=SecureVerificationTokenProvider(),
            email_sender=SmtpEmailSender(app_settings),
            public_web_url=app_settings.public_web_url,
            token_lifetime=timedelta(
                hours=app_settings.verification_token_lifetime_hours
            ),
        )
    )
    access_unit_of_work_factory = create_access_unit_of_work_factory(engine)
    app.state.authorization_service = (
        authorization_service
        if authorization_service is not None
        else AuthorizationService(
            membership_unit_of_work_factory=access_unit_of_work_factory
        )
    )
    sources_unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    app.state.upload_dictionary_service = (
        upload_dictionary_service
        if upload_dictionary_service is not None
        else UploadDictionaryService(
            unit_of_work_factory=sources_unit_of_work_factory,
            object_storage=app.state.object_storage,
            inspection_queue=CeleryInspectionQueue(create_celery_client(app_settings)),
            max_upload_size_bytes=app_settings.max_upload_size_bytes,
        )
    )
    app.state.save_dictionary_metadata_service = (
        save_dictionary_metadata_service
        if save_dictionary_metadata_service is not None
        else SaveDictionaryMetadataService(
            unit_of_work_factory=sources_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.get_dictionary_service = (
        get_dictionary_service
        if get_dictionary_service is not None
        else GetDictionaryService(
            unit_of_work_factory=sources_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.delete_dictionary_service = (
        delete_dictionary_service
        if delete_dictionary_service is not None
        else DeleteDictionaryService(
            unit_of_work_factory=sources_unit_of_work_factory,
            object_storage=app.state.object_storage,
            authorization=app.state.authorization_service,
        )
    )
    app.state.dictionary_readiness_service = (
        dictionary_readiness_service
        if dictionary_readiness_service is not None
        else DictionaryReadinessService(
            unit_of_work_factory=sources_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.save_page_ranges_service = (
        save_page_ranges_service
        if save_page_ranges_service is not None
        else SavePageRangesService(
            unit_of_work_factory=sources_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.mark_dictionary_scanned_service = (
        mark_dictionary_scanned_service
        if mark_dictionary_scanned_service is not None
        else MarkDictionaryScannedService(
            unit_of_work_factory=sources_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.advance_dictionary_processing_status_service = (
        advance_dictionary_processing_status_service
        if advance_dictionary_processing_status_service is not None
        else AdvanceDictionaryProcessingStatusService(
            unit_of_work_factory=sources_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.publish_dictionary_service = (
        publish_dictionary_service
        if publish_dictionary_service is not None
        else PublishDictionaryService(
            unit_of_work_factory=sources_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    lexicography_unit_of_work_factory = create_lexicography_unit_of_work_factory(engine)
    reference_lexicon_unit_of_work_factory = (
        create_reference_lexicon_unit_of_work_factory(engine)
    )
    app.state.reference_lexicon_query_service = (
        reference_lexicon_query_service
        if reference_lexicon_query_service is not None
        else ReferenceLexiconQueryService(reference_lexicon_unit_of_work_factory)
    )
    reference_link_unit_of_work_factory = (
        create_entry_reference_link_unit_of_work_factory(engine)
    )
    app.state.manage_entry_reference_links_service = (
        manage_entry_reference_links_service
        if manage_entry_reference_links_service is not None
        else ManageEntryReferenceLinksService(
            lexicography_unit_of_work_factory=lexicography_unit_of_work_factory,
            reference_link_unit_of_work_factory=reference_link_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
            reference_lexicon=app.state.reference_lexicon_query_service,
        )
    )
    app.state.create_lexeme_service = (
        create_lexeme_service
        if create_lexeme_service is not None
        else CreateLexemeService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.lexeme_query_service = (
        lexeme_query_service
        if lexeme_query_service is not None
        else LexemeQueryService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.update_lexeme_service = (
        update_lexeme_service
        if update_lexeme_service is not None
        else UpdateLexemeService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.delete_lexeme_service = (
        delete_lexeme_service
        if delete_lexeme_service is not None
        else DeleteLexemeService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.scan_progress_service = (
        scan_progress_service
        if scan_progress_service is not None
        else ScanProgressService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
            status_service=app.state.advance_dictionary_processing_status_service,
        )
    )
    app.state.finish_scanning_service = (
        finish_scanning_service
        if finish_scanning_service is not None
        else FinishScanningService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
            scanning_service=app.state.mark_dictionary_scanned_service,
        )
    )
    app.state.suggest_lexemes_service = (
        suggest_lexemes_service
        if suggest_lexemes_service is not None
        else SuggestLexemesService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
            queue=CeleryOcrSuggestionQueue(create_celery_client(app_settings)),
        )
    )
    app.state.queue_dictionary_scan_service = (
        queue_dictionary_scan_service
        if queue_dictionary_scan_service is not None
        else QueueDictionaryScanService(
            dictionary_pages=app.state.get_dictionary_service,
            queue=CeleryDictionaryScanQueue(create_celery_client(app_settings)),
        )
    )
    app.state.queue_article_schema_generation_service = (
        queue_article_schema_generation_service
        if queue_article_schema_generation_service is not None
        else QueueArticleSchemaGenerationService(
            dictionary_pages=app.state.get_dictionary_service,
            queue=CeleryArticleSchemaQueue(create_celery_client(app_settings)),
        )
    )
    app.state.activate_article_schema_service = (
        activate_article_schema_service
        if activate_article_schema_service is not None
        else ActivateArticleSchemaService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.save_article_schema_service = (
        save_article_schema_service
        if save_article_schema_service is not None
        else SaveArticleSchemaService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.promote_lexeme_to_entry_service = (
        promote_lexeme_to_entry_service
        if promote_lexeme_to_entry_service is not None
        else PromoteLexemeToEntryService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.queue_entry_field_extraction_service = (
        queue_entry_field_extraction_service
        if queue_entry_field_extraction_service is not None
        else QueueEntryFieldExtractionService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
            queue=CeleryEntryExtractionQueue(create_celery_client(app_settings)),
        )
    )
    app.state.create_entry_field_service = (
        create_entry_field_service
        if create_entry_field_service is not None
        else CreateEntryFieldService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.update_entry_field_service = (
        update_entry_field_service
        if update_entry_field_service is not None
        else UpdateEntryFieldService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.delete_entry_field_service = (
        delete_entry_field_service
        if delete_entry_field_service is not None
        else DeleteEntryFieldService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.validate_entry_service = (
        validate_entry_service
        if validate_entry_service is not None
        else ValidateEntryService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.render_entry_service = (
        render_entry_service
        if render_entry_service is not None
        else RenderEntryService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
            renderer=Jinja2EntryPresentationRenderer(),
        )
    )
    app.state.entry_query_service = (
        entry_query_service
        if entry_query_service is not None
        else EntryQueryService(
            unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_pages=app.state.get_dictionary_service,
        )
    )
    app.state.review_service = (
        review_service
        if review_service is not None
        else ReviewService(
            review_unit_of_work_factory=create_review_unit_of_work_factory(engine),
            lexicography_unit_of_work_factory=lexicography_unit_of_work_factory,
            dictionary_service=app.state.get_dictionary_service,
            authorization=app.state.authorization_service,
            validate_service=app.state.validate_entry_service,
        )
    )
    app.state.processing_task_service = (
        processing_task_service
        if processing_task_service is not None
        else ProcessingTaskService(
            create_processing_unit_of_work_factory(engine),
            reenqueuers={
                ProcessingTaskKind.DICTIONARY_SCAN: (
                    lambda task, actor: app.state.queue_dictionary_scan_service.enqueue(
                        task.dictionary_id, actor
                    )
                ),
                ProcessingTaskKind.ARTICLE_SCHEMA_GENERATION: (
                    lambda task, actor: (
                        app.state.queue_article_schema_generation_service.enqueue(
                            task.dictionary_id, actor
                        )
                    )
                ),
                ProcessingTaskKind.ENTRY_EXTRACTION: (
                    lambda task, actor: (
                        app.state.queue_entry_field_extraction_service.enqueue(
                            task.target_id, actor
                        )
                    )
                ),
                ProcessingTaskKind.OCR_SUGGESTIONS: (
                    lambda task, actor: app.state.suggest_lexemes_service.enqueue(
                        task.dictionary_id,
                        actor,
                        int(str(task.rerun_params.get("page_number", 0))),
                    )
                ),
            },
        )
    )
    app.state.abbreviation_crud_service = (
        abbreviation_crud_service
        if abbreviation_crud_service is not None
        else AbbreviationCrudService(
            unit_of_work_factory=sources_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.abbreviation_import_service = (
        abbreviation_import_service
        if abbreviation_import_service is not None
        else AbbreviationImportService(
            unit_of_work_factory=sources_unit_of_work_factory,
        )
    )
    app.state.manage_members_service = (
        manage_members_service
        if manage_members_service is not None
        else ManageMembersService(
            unit_of_work_factory=access_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.list_members_service = (
        list_members_service
        if list_members_service is not None
        else ListMembersService(
            unit_of_work_factory=access_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.include_router(create_health_router(app_settings))
    app.include_router(
        create_auth_router(
            app.state.registration_service,
            app.state.authentication_service,
            app.state.password_reset_service,
            app.state.account_service,
            session_lifetime=timedelta(hours=app_settings.session_lifetime_hours),
            secure_cookie=app_settings.environment.value in {"staging", "production"},
        )
    )
    if app.state.google_authentication_service is not None:
        app.include_router(
            create_google_oauth_router(
                app.state.google_authentication_service,
                session_lifetime=timedelta(hours=app_settings.session_lifetime_hours),
                secure_cookie=app_settings.environment.value
                in {"staging", "production"},
                public_web_url=app_settings.public_web_url,
            )
        )
    app.include_router(create_tasks_router(app.state.task_queue))
    app.include_router(
        create_dictionaries_router(
            app.state.authentication_service,
            app.state.upload_dictionary_service,
            app.state.save_dictionary_metadata_service,
            app.state.get_dictionary_service,
            app.state.object_storage,
            app.state.delete_dictionary_service,
            app.state.dictionary_readiness_service,
        )
    )
    app.include_router(
        create_project_members_router(
            app.state.authentication_service,
            app.state.get_dictionary_service,
            app.state.manage_members_service,
            app.state.list_members_service,
            unit_of_work_factory,
        )
    )
    app.include_router(
        create_page_ranges_router(
            app.state.authentication_service,
            app.state.get_dictionary_service,
            app.state.save_page_ranges_service,
        )
    )
    app.include_router(
        create_pages_router(
            app.state.authentication_service,
            app.state.get_dictionary_service,
            app.state.object_storage,
        )
    )
    app.include_router(
        create_lexemes_router(
            app.state.authentication_service,
            app.state.create_lexeme_service,
            app.state.lexeme_query_service,
        )
    )
    app.include_router(
        create_lexeme_management_router(
            app.state.authentication_service,
            app.state.update_lexeme_service,
            app.state.delete_lexeme_service,
        )
    )
    app.include_router(
        create_scan_progress_router(
            app.state.authentication_service,
            app.state.scan_progress_service,
        )
    )
    app.include_router(
        create_finish_scanning_router(
            app.state.authentication_service,
            app.state.finish_scanning_service,
        )
    )
    app.include_router(
        create_publish_dictionary_router(
            app.state.authentication_service,
            app.state.publish_dictionary_service,
        )
    )
    app.include_router(
        create_ocr_suggestions_router(
            app.state.authentication_service,
            app.state.suggest_lexemes_service,
            app.state.processing_task_service,
        )
    )
    app.include_router(
        create_ocr_scan_router(
            app.state.authentication_service,
            app.state.queue_dictionary_scan_service,
            app.state.processing_task_service,
        )
    )
    app.include_router(
        create_abbreviations_router(
            app.state.authentication_service,
            app.state.abbreviation_crud_service,
            app.state.abbreviation_import_service,
        )
    )
    app.include_router(
        create_article_schemas_router(
            app.state.authentication_service,
            app.state.queue_article_schema_generation_service,
            app.state.activate_article_schema_service,
            app.state.save_article_schema_service,
            app.state.processing_task_service,
        )
    )
    app.include_router(
        create_entries_router(
            app.state.authentication_service,
            app.state.promote_lexeme_to_entry_service,
            app.state.queue_entry_field_extraction_service,
            app.state.create_entry_field_service,
            app.state.update_entry_field_service,
            app.state.delete_entry_field_service,
            app.state.validate_entry_service,
            app.state.render_entry_service,
            app.state.entry_query_service,
            app.state.get_dictionary_service,
            app.state.processing_task_service,
        )
    )
    app.include_router(
        create_review_router(
            app.state.authentication_service,
            app.state.review_service,
        )
    )
    app.include_router(
        create_processing_tasks_router(
            app.state.authentication_service,
            app.state.get_dictionary_service,
            app.state.processing_task_service,
        )
    )
    app.include_router(
        create_reference_lexicons_router(
            app.state.authentication_service,
            app.state.reference_lexicon_query_service,
            app.state.manage_entry_reference_links_service,
        )
    )
    geography_unit_of_work_factory = create_geography_unit_of_work_factory(engine)
    app.state.geography_query_service = (
        geography_query_service
        if geography_query_service is not None
        else GeographyQueryService(
            unit_of_work_factory=geography_unit_of_work_factory,
        )
    )
    app.include_router(
        create_geography_router(
            app.state.authentication_service,
            app.state.geography_query_service,
        )
    )
    app.state.settlement_mapping_crud_service = (
        settlement_mapping_crud_service
        if settlement_mapping_crud_service is not None
        else SettlementMappingCrudService(
            unit_of_work_factory=sources_unit_of_work_factory,
            geography_unit_of_work_factory=geography_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.settlement_search_service = (
        settlement_search_service
        if settlement_search_service is not None
        else SettlementSearchService(
            geography_unit_of_work_factory=geography_unit_of_work_factory,
        )
    )
    app.state.settlement_confirmation_service = (
        settlement_confirmation_service
        if settlement_confirmation_service is not None
        else SettlementConfirmationService(
            unit_of_work_factory=sources_unit_of_work_factory,
            geography_unit_of_work_factory=geography_unit_of_work_factory,
            authorization=app.state.authorization_service,
        )
    )
    app.state.settlement_mapping_import_service = (
        settlement_mapping_import_service
        if settlement_mapping_import_service is not None
        else SettlementMappingImportService(
            unit_of_work_factory=sources_unit_of_work_factory,
        )
    )
    app.include_router(
        create_settlements_router(
            app.state.authentication_service,
            app.state.settlement_mapping_crud_service,
            app.state.settlement_search_service,
            app.state.settlement_confirmation_service,
            app.state.settlement_mapping_import_service,
        )
    )
    return app
