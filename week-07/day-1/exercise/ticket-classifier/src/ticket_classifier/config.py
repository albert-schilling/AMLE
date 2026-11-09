from functools import cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: SecretStr
    model: str = "claude-haiku-4-5"
    max_tokens: int = 200


@cache
def get_settings() -> Settings:
    """Load settings once; the environment and .env are read on first use."""
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment
