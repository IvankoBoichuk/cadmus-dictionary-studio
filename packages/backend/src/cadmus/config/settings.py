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
