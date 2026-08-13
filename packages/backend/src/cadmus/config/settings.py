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
