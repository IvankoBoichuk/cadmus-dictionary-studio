"""Environment-backed application settings."""

from enum import StrEnum

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlalchemy.engine import make_url


class Environment(StrEnum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Typed, environment-backed metadata shared by process entrypoints."""

    model_config = SettingsConfigDict(
        env_prefix="CADMUS_",
        case_sensitive=False,
        extra="ignore",
        str_strip_whitespace=True,
        env_ignore_empty=True,
    )

    name: str = Field(default="cadmus-api", min_length=1)
    environment: Environment = Environment.DEVELOPMENT
    version: str = Field(default="0.1.0", min_length=1)
    database_name: str = Field(default="cadmus", min_length=1)
    database_user: str = Field(default="cadmus", min_length=1)
    database_password: SecretStr = Field(
        default=SecretStr("cadmus-local"),
        min_length=1,
    )
    database_host: str = Field(default="localhost", min_length=1)
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_url: SecretStr | None = None
    redis_host: str = Field(default="localhost", min_length=1)
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_broker_database: int = Field(default=0, ge=0)
    redis_result_database: int = Field(default=1, ge=0)
    redis_broker_url: SecretStr | None = None
    redis_result_backend_url: SecretStr | None = None
    object_storage_endpoint: str = Field(default="localhost:9000", min_length=1)
    object_storage_access_key: SecretStr = Field(
        default=SecretStr("cadmus-local-access"),
        min_length=3,
    )
    object_storage_secret_key: SecretStr = Field(
        default=SecretStr("cadmus-local-secret"),
        min_length=8,
    )
    object_storage_bucket: str = Field(default="cadmus", min_length=3)
    object_storage_secure: bool = False
    max_upload_size_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    public_web_url: str = Field(default="http://localhost:5173", min_length=1)
    verification_token_lifetime_hours: int = Field(default=24, ge=1, le=168)
    password_reset_token_lifetime_hours: int = Field(default=1, ge=1, le=168)
    session_lifetime_hours: int = Field(default=12, ge=1, le=168)
    smtp_host: str = Field(default="localhost", min_length=1)
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = False
    smtp_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    email_from: str = Field(default="Cadmus <noreply@cadmus.local>", min_length=3)
    geography_api_graphql_url: str = Field(
        default="https://decentralization.ua/graphql", min_length=1
    )
    geography_api_rest_base_url: str = Field(
        default="https://decentralization.ua/api/v1", min_length=1
    )
    geography_api_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    geography_api_max_retries: int = Field(default=3, ge=0, le=5)
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    google_oauth_redirect_url: str | None = None
    google_oauth_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    ocr_task_timeout_seconds: float = Field(default=25.0, gt=0, le=60)

    def sqlalchemy_database_url(self) -> URL:
        """Return the single effective database URL without logging credentials."""
        if self.database_url is not None:
            return make_url(self.database_url.get_secret_value())

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )

    def celery_broker_url(self) -> str:
        """Return the effective Redis broker URL for Celery."""
        if self.redis_broker_url is not None:
            return self.redis_broker_url.get_secret_value()
        return (
            f"redis://{self.redis_host}:{self.redis_port}/{self.redis_broker_database}"
        )

    def celery_result_backend_url(self) -> str:
        """Return the effective Redis result backend URL for Celery."""
        if self.redis_result_backend_url is not None:
            return self.redis_result_backend_url.get_secret_value()
        return (
            f"redis://{self.redis_host}:{self.redis_port}/{self.redis_result_database}"
        )
