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

from .checkpoint import thread_config
from .config import Settings
from .models import TriageState

# Only our own loggers go to Loki: not the SDK's export logs (no feedback loop), not
# TraceVerde's or the Anthropic SDK's.
APP_LOGGER = "ticket_classifier"
OTEL_HANDLER_NAME = "ticket_classifier.otel"
# extra= for a log line with ticket, customer or reviewer text: it stays on the
# console and is not sent to Loki.
CONSOLE_ONLY = {"console_only": True}

TicketStatus = Literal["finished", "paused", "failed"]

# A no-op tracer while telemetry is off; becomes real once a provider is set.
tracer = trace.get_tracer(__name__)
# ticket_id and thread_id of the ticket being worked on, for its log records.
TICKET_LOG_FIELDS: ContextVar[dict[str, str]] = ContextVar("ticket_log_fields")

# Fixed for privacy, whatever the environment says: no prompt or answer text in the
# spans, no data to any endpoint other than our collector, no model downloads, no
# usage report to the TraceVerde maintainers.
PRIVACY_ENVIRONMENT = {
    "GENAI_ENABLE_CONTENT_CAPTURE": "false",
    "GENAI_ALLOW_EXTERNAL_EGRESS": "false",
    "GENAI_AIR_GAPPED": "true",
    "TRACEVERDE_TELEMETRY": "false",
}

# Only what this app uses: no GPU polling, no database or HTTP client spans.
SCOPE_ENVIRONMENT = {
    "GENAI_ENABLED_INSTRUMENTORS": "anthropic,langgraph",
    "GENAI_ENABLE_GPU_METRICS": "false",
    "GENAI_ENABLE_MCP_INSTRUMENTATION": "false",
    # TraceVerde turns exemplars off by default; they link metrics to traces.
    "OTEL_METRICS_EXEMPLAR_FILTER": "trace_based",
}


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
    there first.
    """
    if not settings.otel_enabled:
        return
    os.environ.update(telemetry_environment(settings))

    import genai_otel  # only when enabled: it sets up global OTel providers

    genai_otel.instrument()
    # The same resource as the traces, so logs and spans name the same service.
    resource = trace.get_tracer_provider().resource
    attach_log_handler(log_exporter(settings), resource)


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
    for handler in app_logger.handlers[:]:
        if handler.get_name() == OTEL_HANDLER_NAME:
            app_logger.removeHandler(handler)
    # DEBUG lines hold whole graph states, with customer data.
    handler = LoggingHandler(level=logging.INFO, logger_provider=provider)
    handler.set_name(OTEL_HANDLER_NAME)
    handler.addFilter(drop_console_only)
    handler.addFilter(add_ticket_fields)
    app_logger.addHandler(handler)
    return provider


def drop_console_only(record: logging.LogRecord) -> bool:
    """Log filter: keep lines marked ``CONSOLE_ONLY`` out of the export."""
    return not getattr(record, "console_only", False)


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


def record_classification(state: TriageState) -> None:
    """Put category and priority on the current span, once the state has them."""

    classification = state.get("classification")

    if classification is not None:
        trace.get_current_span().set_attributes(
            {
                "category": classification.category,
                "priority": classification.priority,
            }
        )


def record_status(status: TicketStatus) -> None:
    """Put the ticket's outcome on its span. A pause is not an error."""
    trace.get_current_span().set_attribute("ticket.status", status)


def record_reused(status: TicketStatus) -> None:
    """This run did no work on the ticket: it only read the saved status."""
    record_status(status)
    trace.get_current_span().set_attribute("ticket.reused", True)


def record_pause(node: str) -> None:
    """Mark the ticket's span, and record the moment this run paused at ``node``."""
    record_status("paused")
    trace.get_current_span().add_event("paused", {"node": node})
