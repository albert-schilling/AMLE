"""OpenTelemetry: hand the settings to the SDK, start TraceVerde, send our logs.

TraceVerde (genai_otel) instruments the Anthropic client and the LangGraph run and
node methods, for traces and metrics. The client must be created after
``configure_telemetry``; ``get_client()`` is lazy, so it is. TraceVerde sends no
logs, so ``attach_log_handler`` does.
"""

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.metadata import version
from typing import Literal

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    ConsoleLogRecordExporter,
    LogRecordExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode

from .checkpoint import thread_config
from .config import Settings
from .models import TriageState

# Only our own loggers go to Loki: not the SDK's export logs (no feedback loop), not
# TraceVerde's or the Anthropic SDK's.
APP_LOGGER = "ticket_classifier"
OTEL_HANDLER_NAME = "ticket_classifier.otel"
# Marks a log line as safe for Loki: only ids, counts and labels, never file paths or
# ticket, customer, reviewer or error text. Use it through ``get_loggers``; unmarked
# lines stay on the console.
EXPORT_LOG = {"export_log": True}

TicketStatus = Literal["finished", "paused", "failed"]

# A no-op tracer while telemetry is off; becomes real once a provider is set.
tracer = trace.get_tracer(__name__)
# ticket_id and thread_id of the ticket being worked on, for its log records.
TICKET_LOG_FIELDS: ContextVar[dict[str, str]] = ContextVar("ticket_log_fields")

# Fixed for privacy, whatever the environment says: no prompt or answer text in the
# spans, no data to any endpoint other than our collector, no model downloads, no
# usage report to the TraceVerde maintainers.
PRIVACY_ENVIRONMENT = {
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "NO_CONTENT",
    "GENAI_ENABLE_CONTENT_CAPTURE": "false",
    "GENAI_OTEL_MEDIA_CAPTURE_MODE": "off",
    "GENAI_CAPTURE_RESPONSE_HEADERS": "",
    "GENAI_ROUTER_RESPONSE_HEADERS": "",
    "GENAI_ALLOW_EXTERNAL_EGRESS": "false",
    "GENAI_AIR_GAPPED": "true",
    "TRACEVERDE_TELEMETRY": "false",
}

# These would send telemetry past OTEL_EXPORTER_OTLP_ENDPOINT or add credentials.
OTLP_OVERRIDES = (
    "OTEL_EXPORTER_OTLP_HEADERS",
    *(
        f"OTEL_EXPORTER_OTLP_{signal}_{option}"
        for signal in ("TRACES", "METRICS", "LOGS")
        for option in ("ENDPOINT", "HEADERS", "PROTOCOL")
    ),
)

# Only what this app uses: no GPU polling, no database or HTTP client spans.
SCOPE_ENVIRONMENT = {
    "GENAI_ENABLED_INSTRUMENTORS": "anthropic,langgraph",
    "GENAI_ENABLE_GPU_METRICS": "false",
    "GENAI_ENABLE_MCP_INSTRUMENTATION": "false",
    # TraceVerde turns exemplars off by default; they link metrics to traces.
    "OTEL_METRICS_EXEMPLAR_FILTER": "trace_based",
}


class TelemetrySetupError(RuntimeError):
    """Telemetry is on, but TraceVerde could not set it up."""


def telemetry_environment(settings: Settings) -> dict[str, str]:
    """The env vars the OTel SDK and TraceVerde read, built from the settings."""
    resource_attributes = ",".join(
        part
        for part in (
            settings.otel_resource_attributes,
            f"service.version={version('ticket-classifier')}",
        )
        if part
    )
    return {
        "OTEL_SERVICE_NAME": settings.otel_service_name,
        "OTEL_EXPORTER_OTLP_ENDPOINT": settings.otel_exporter_otlp_endpoint,
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_RESOURCE_ATTRIBUTES": resource_attributes,
        **SCOPE_ENVIRONMENT,
        **PRIVACY_ENVIRONMENT,
    }


def configure_telemetry(settings: Settings) -> None:
    """Start traces, metrics and logs if ``otel_enabled``; otherwise do nothing.

    The SDK reads only ``os.environ``, not ``.env``, so the settings are written
    there first. Raises ``TelemetrySetupError`` if TraceVerde could not start.
    """
    if not settings.otel_enabled:
        return
    for name in OTLP_OVERRIDES:
        os.environ.pop(name, None)
    os.environ.update(telemetry_environment(settings))

    import genai_otel  # only when enabled: it sets up global OTel providers

    genai_otel.instrument()  # type: ignore[no-untyped-call]  # TraceVerde has no hints
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):  # it logs setup errors, no raise
        raise TelemetrySetupError("TraceVerde could not start, see the log above")
    # The same resource as the traces, so logs and spans name the same service.
    attach_log_handler(log_exporter(settings), provider.resource)


def log_exporter(settings: Settings) -> LogRecordExporter:
    """OTLP to the collector, or the console if the endpoint is empty."""
    if settings.otel_exporter_otlp_endpoint == "":
        return ConsoleLogRecordExporter()
    return OTLPLogExporter()  # reads OTEL_EXPORTER_OTLP_ENDPOINT, adds /v1/logs


def attach_log_handler(
    exporter: LogRecordExporter, resource: Resource
) -> LoggerProvider:
    """Send our log records to ``exporter``, with the current span's trace and span id.

    Returns the provider (to flush it). Safe to call again: an earlier handler is
    replaced.
    """
    provider = LoggerProvider(resource=resource)  # flushes at exit
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    app_logger = logging.getLogger(APP_LOGGER)
    for old_handler in app_logger.handlers[:]:
        if old_handler.get_name() == OTEL_HANDLER_NAME:
            app_logger.removeHandler(old_handler)
    handler = LoggingHandler(level=logging.INFO, logger_provider=provider)
    handler.set_name(OTEL_HANDLER_NAME)
    handler.addFilter(export_marked_only)
    handler.addFilter(add_ticket_fields)
    app_logger.addHandler(handler)
    return provider


def get_loggers(
    name: str,
) -> tuple[logging.Logger, logging.LoggerAdapter[logging.Logger]]:
    """Two loggers for a module: console only, and console plus Loki.

    Use the second only for ids, counts and labels.
    """
    logger = logging.getLogger(name)
    return logger, logging.LoggerAdapter(logger, EXPORT_LOG)


def export_marked_only(record: logging.LogRecord) -> bool:
    """Log filter: export only lines marked ``EXPORT_LOG``, without the marker."""
    return bool(vars(record).pop("export_log", False))


def add_ticket_fields(record: logging.LogRecord) -> bool:
    """Log filter: add the current ticket's ids; they become log attributes."""
    vars(record).update(TICKET_LOG_FIELDS.get({}))
    return True


@contextmanager
def ticket_span(
    ticket_id: str, run_mode: Literal["run", "resume"]
) -> Generator[trace.Span]:
    """One ticket's work: a span with its ids, which its log records get too.

    The span name has no ticket id: Tempo turns span names into a metric label.
    """

    fields = {
        "ticket_id": ticket_id,
        "thread_id": thread_config(ticket_id)["configurable"]["thread_id"],
    }
    attributes = {**fields, "run_mode": run_mode}

    with tracer.start_as_current_span(
        f"ticket.{run_mode}", attributes=attributes
    ) as span:
        token = TICKET_LOG_FIELDS.set(fields)
        try:
            yield span
        finally:
            TICKET_LOG_FIELDS.reset(token)


def record_state(state: TriageState) -> None:
    """Put what the state has so far on the current span: policy passages, retrieval
    attempts and verdict, category, priority and the reply's citations.

    Passages and reply only as citations, counts and scores: their text, the quotes
    and the search queries stay out.
    """
    span = trace.get_current_span()

    retrieval = state.get("retrieval")
    result = retrieval.result if retrieval is not None else None
    if result is not None:
        passages = result.passages
        span.set_attributes(
            {
                "knowledge.passages": len(passages),
                "knowledge.dropped": result.dropped,
                "knowledge.sources": [passage.citation for passage in passages],
            }
        )
        if passages:
            span.set_attribute("knowledge.top_score", passages[0].score)

    classification = state.get("classification")

    if classification is not None:
        span.set_attributes(
            {
                "category": classification.category,
                "priority": classification.priority,
            }
        )

    if retrieval is not None and retrieval.attempts:
        span.set_attribute("knowledge.attempts", retrieval.attempts)
    if retrieval is not None and retrieval.ok is not None:
        span.set_attribute("knowledge.retrieval_ok", retrieval.ok)

    reply = state.get("reply")
    if reply is not None:
        span.set_attributes(
            {
                "reply.citations": len(reply.citations),
                "reply.sources": [citation.citation for citation in reply.citations],
                "reply.has_sources": reply.has_sources,
            }
        )


def record_status(status: TicketStatus) -> None:
    """Put the ticket's outcome on its span. A pause is not an error."""
    trace.get_current_span().set_attribute("ticket.status", status)


def record_failure(error: Exception) -> None:
    """Mark the ticket as failed. Only the error type: its text can quote data."""
    error_type = type(error).__name__
    record_status("failed")
    span = trace.get_current_span()
    span.add_event("exception", {"exception.type": error_type})
    span.set_status(Status(StatusCode.ERROR, error_type))


def record_reused(status: TicketStatus) -> None:
    """This run did no work on the ticket: it only read the saved status."""
    record_status(status)
    trace.get_current_span().set_attribute("ticket.reused", True)


def record_pause(node: str) -> None:
    """Mark the ticket's span, and record the moment this run paused at ``node``."""
    record_status("paused")
    trace.get_current_span().add_event("paused", {"node": node})
