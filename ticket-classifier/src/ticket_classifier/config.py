from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: SecretStr | None = None  # needed only for model calls
    model: str = "claude-haiku-4-5"
    max_tokens: int = 4_000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_file: Path | None = None  # also write the logs to this file, if set
    trace_file: Path = Path("output/trace.jsonl")  # one JSON line per workflow event
    tickets_path: Path = Path("fixtures/tickets.json")
    customers_path: Path = Path("fixtures/customers.json")
    results_path: Path = Path("output/results.json")
    graph_path: Path = Path("output/graph.mmd")  # mermaid diagram of the workflow
    checkpoint_path: Path = Path("output/checkpoints.db")  # saved workflow runs

    # OpenTelemetry (traces, metrics, logs). The names are the standard OTEL_* env
    # vars; the SDK reads only os.environ, so these values are handed to it at start.
    otel_enabled: bool = False  # off: no instrumentation, nothing is sent
    otel_service_name: str = "ticket-classifier"
    # OTLP HTTP endpoint of the collector; "" prints telemetry to the console.
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    # Extra resource attributes, "key=value,key=value". service.version comes from
    # the package version.
    otel_resource_attributes: str = (
        "service.namespace=amle,deployment.environment.name=local"
    )


@cache
def get_settings() -> Settings:
    """Load settings once; the environment and .env are read on first use."""
    return Settings()
