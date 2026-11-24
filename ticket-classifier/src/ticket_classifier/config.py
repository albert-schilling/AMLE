from functools import cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
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

    # Knowledge base: policy documents, embedded locally, stored in PostgreSQL.
    # postgresql://user:password@localhost:5432/knowledge, see database/.env.
    # Needed only for the knowledge base.
    knowledge_database_url: SecretStr | None = None
    knowledge_base_path: Path = Path("data/knowledge_base")  # one .md file per policy

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Not fastembed's default (the temp dir), so the model is downloaded only once.
    embedding_cache_path: Path = Path("output/fastembed")
    chunk_size: int = Field(default=60, gt=0)  # words per chunk
    # Words shared by neighboring chunks. 60/20 from make kb-eval, see plan_w9d1.md.
    chunk_overlap: int = Field(default=20, ge=0)
    knowledge_top_k: int = Field(default=3, gt=0)  # passages per ticket
    # Labelled questions for make kb-eval; outside the knowledge base, never indexed.
    knowledge_questions_path: Path = Path("data/eval/knowledge_questions.json")

    @model_validator(mode="after")
    def overlap_smaller_than_chunk(self) -> Self:
        """Each chunk must start after the previous one, or chunking never ends."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


@cache
def get_settings() -> Settings:
    """Load settings once; the environment and .env are read on first use."""
    return Settings()
