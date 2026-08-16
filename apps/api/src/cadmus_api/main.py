"""FastAPI application composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from cadmus.config import Settings
from cadmus.identity import (
    AuthenticationService,
    PasswordResetService,
    RegistrationService,
)
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.email import SmtpEmailSender
from cadmus.infrastructure.identity import create_identity_unit_of_work_factory
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
from cadmus.processing import TaskQueue
from cadmus.sources import (
    AbbreviationCrudService,
    AbbreviationImportService,
    DeleteDictionaryService,
    GetDictionaryService,
    ObjectStorage,
    SaveDictionaryMetadataService,
    UploadDictionaryService,
)
from fastapi import FastAPI
from sqlalchemy import Engine, text

from cadmus_api.routes.abbreviations import create_abbreviations_router
from cadmus_api.routes.auth import create_auth_router
from cadmus_api.routes.dictionaries import create_dictionaries_router
from cadmus_api.routes.health import create_health_router
from cadmus_api.routes.tasks import create_tasks_router


def create_app(
    settings: Settings | None = None,
    database_engine: Engine | None = None,
    task_queue: TaskQueue | None = None,
    object_storage: ObjectStorage | None = None,
    registration_service: RegistrationService | None = None,
    authentication_service: AuthenticationService | None = None,
    password_reset_service: PasswordResetService | None = None,
    upload_dictionary_service: UploadDictionaryService | None = None,
    save_dictionary_metadata_service: SaveDictionaryMetadataService | None = None,
    get_dictionary_service: GetDictionaryService | None = None,
    delete_dictionary_service: DeleteDictionaryService | None = None,
    abbreviation_crud_service: AbbreviationCrudService | None = None,
    abbreviation_import_service: AbbreviationImportService | None = None,
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
    app.include_router(create_tasks_router(app.state.task_queue))
    app.include_router(
        create_dictionaries_router(
            app.state.authentication_service,
            app.state.upload_dictionary_service,
            app.state.save_dictionary_metadata_service,
            app.state.get_dictionary_service,
            app.state.object_storage,
            app.state.delete_dictionary_service,
        )
    )
    app.include_router(
        create_abbreviations_router(
            app.state.authentication_service,
            app.state.abbreviation_crud_service,
            app.state.abbreviation_import_service,
        )
    )
    return app
