from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_THINKING_BUDGET = 1024  # API minimum for extended thinking


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: SecretStr
    model: str = "claude-haiku-4-5"
    max_tokens: int = 4_000
    max_iterations: int = 6  # hard cap of the agent loop; hitting it escalates
    thinking_budget: int = 2_000  # extended thinking tokens per reply; 0 = off
    # "server": Anthropic's sandboxed web_fetch; "local": our own httpx tool
    fetch_backend: Literal["server", "local"] = "server"
    status_domain: str = "status.mollie.com"  # a domain web_fetch may reach
    status_url: str = "https://status.mollie.com/api/v2/components.json"
    # fake payments file on GitHub Pages (docs/payments.json); bare domain only,
    # the API refuses a path in allowed_domains
    payments_domain: str = "albert-schilling.github.io"
    payments_url: str = "https://albert-schilling.github.io/AMLE/payments.json"
    web_fetch_max_uses: int = 3  # web_fetch calls per ticket
    web_fetch_max_content_tokens: int = 8_000  # cap on the fetched page size
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_file: Path | None = None  # also write logs and trace here, if set
    log_path: Path = Path(
        "fixtures/sample_app.log"
    )  # uploaded to the sandbox if it exists
    tickets_path: Path = Path("fixtures/tickets.json")
    customers_path: Path = Path("fixtures/customers.json")
    results_path: Path = Path("output/results.json")

    @model_validator(mode="after")
    def _check_thinking_budget(self) -> Settings:
        if self.thinking_budget == 0:
            return self
        if self.thinking_budget < MIN_THINKING_BUDGET:
            raise ValueError(f"THINKING_BUDGET must be 0 or >= {MIN_THINKING_BUDGET}")
        if self.thinking_budget >= self.max_tokens:
            raise ValueError("THINKING_BUDGET must be below MAX_TOKENS")
        return self


@cache
def get_settings() -> Settings:
    """Load settings once; the environment and .env are read on first use."""
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment
