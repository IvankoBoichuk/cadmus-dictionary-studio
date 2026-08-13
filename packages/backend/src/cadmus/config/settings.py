"""Environment-backed application settings."""

from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
