"""FastAPI application composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from cadmus.config import Settings
from cadmus.geography import GeographyQueryService
from cadmus.identity import (
    AuthenticationService,
    GoogleAuthenticationService,
    PasswordResetService,
    RegistrationService,
)
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.email import SmtpEmailSender
from cadmus.infrastructure.geography import create_geography_unit_of_work_factory
from cadmus.infrastructure.google_oauth import AuthlibGoogleOAuthClient
from cadmus.infrastructure.identity import create_identity_unit_of_work_factory
from cadmus.infrastructure.lexicography import create_lexicography_unit_of_work_factory
from cadmus.infrastructure.object_storage import create_object_storage
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
    CreateLexemeService,
    DeleteLexemeService,
    FinishScanningService,
    LexemeQueryService,
    ScanProgressService,
    UpdateLexemeService,
)
from cadmus.processing import TaskQueue
from cadmus.sources import (
    AbbreviationCrudService,
    AbbreviationImportService,
    DeleteDictionaryService,
    DictionaryReadinessService,
    GetDictionaryService,
    MarkDictionaryScannedService,
    ObjectStorage,
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
from cadmus_api.routes.auth import create_auth_router
from cadmus_api.routes.dictionaries import create_dictionaries_router
from cadmus_api.routes.finish_scanning import create_finish_scanning_router
from cadmus_api.routes.geography import create_geography_router
from cadmus_api.routes.google_oauth import create_google_oauth_router
from cadmus_api.routes.health import create_health_router
from cadmus_api.routes.lexemes import (
    create_lexeme_management_router,
    create_lexemes_router,
)
from cadmus_api.routes.page_ranges import create_page_ranges_router
from cadmus_api.routes.pages import create_pages_router
from cadmus_api.routes.scan_progress import create_scan_progress_router
from cadmus_api.routes.settlements import create_settlements_router
from cadmus_api.routes.tasks import create_tasks_router


def create_app(
    settings: Settings | None = None,
    database_engine: Engine | None = None,
    task_queue: TaskQueue | None = None,
    object_storage: ObjectStorage | None = None,
    registration_service: RegistrationService | None = None,
    authentication_service: AuthenticationService | None = None,
    google_authentication_service: GoogleAuthenticationService | None = None,
    password_reset_service: PasswordResetService | None = None,
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
    finish_scanning_service: FinishScanningService | None = None,
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
        )
    )
    app.state.get_dictionary_service = (
        get_dictionary_service
        if get_dictionary_service is not None
        else GetDictionaryService(unit_of_work_factory=sources_unit_of_work_factory)
    )
    app.state.delete_dictionary_service = (
        delete_dictionary_service
        if delete_dictionary_service is not None
        else DeleteDictionaryService(
            unit_of_work_factory=sources_unit_of_work_factory,
            object_storage=app.state.object_storage,
        )
    )
    app.state.dictionary_readiness_service = (
        dictionary_readiness_service
        if dictionary_readiness_service is not None
        else DictionaryReadinessService(
            unit_of_work_factory=sources_unit_of_work_factory,
        )
    )
    app.state.save_page_ranges_service = (
        save_page_ranges_service
        if save_page_ranges_service is not None
        else SavePageRangesService(
            unit_of_work_factory=sources_unit_of_work_factory,
        )
    )
    app.state.mark_dictionary_scanned_service = (
        mark_dictionary_scanned_service
        if mark_dictionary_scanned_service is not None
        else MarkDictionaryScannedService(
            unit_of_work_factory=sources_unit_of_work_factory,
        )
    )
    lexicography_unit_of_work_factory = create_lexicography_unit_of_work_factory(engine)
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
    app.state.abbreviation_crud_service = (
        abbreviation_crud_service
        if abbreviation_crud_service is not None
        else AbbreviationCrudService(
            unit_of_work_factory=sources_unit_of_work_factory,
        )
    )
    app.state.abbreviation_import_service = (
        abbreviation_import_service
        if abbreviation_import_service is not None
        else AbbreviationImportService(
            unit_of_work_factory=sources_unit_of_work_factory,
        )
    )
    app.include_router(create_health_router(app_settings))
    app.include_router(
        create_auth_router(
            app.state.registration_service,
            app.state.authentication_service,
            app.state.password_reset_service,
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
        create_abbreviations_router(
            app.state.authentication_service,
            app.state.abbreviation_crud_service,
            app.state.abbreviation_import_service,
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
