import logging
import os

import pytest
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from ticket_classifier.config import Settings
from ticket_classifier.telemetry import (
    APP_LOGGER,
    OTEL_HANDLER_NAME,
    attach_log_handler,
    configure_telemetry,
)


@pytest.fixture
def instrument(mocker):
    """The TraceVerde call, mocked: no global OTel providers or handlers in tests."""
    mocker.patch.dict(os.environ)  # restores env vars written by the code
    mocker.patch("opentelemetry.trace.get_tracer_provider")
    mocker.patch("ticket_classifier.telemetry.attach_log_handler")
    return mocker.patch("genai_otel.instrument")


def test_disabled_starts_nothing_and_leaves_env_alone(instrument):
    before = dict(os.environ)

    configure_telemetry(Settings())

    instrument.assert_not_called()
    assert dict(os.environ) == before


def test_enabled_hands_settings_to_sdk_before_instrumenting(instrument, monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "classifier-test")
    seen = {}
    instrument.side_effect = lambda: seen.update(os.environ)

    configure_telemetry(Settings())

    instrument.assert_called_once()
    assert seen["OTEL_SERVICE_NAME"] == "classifier-test"
    assert seen["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://localhost:4318"


def test_empty_endpoint_is_kept_for_console_output(instrument, monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    configure_telemetry(Settings())

    assert os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] == ""


def test_resource_attributes_keep_ours_and_add_version(instrument, monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "deployment.environment.name=ci")

    configure_telemetry(Settings())

    attributes = dict(
        pair.split("=") for pair in os.environ["OTEL_RESOURCE_ATTRIBUTES"].split(",")
    )
    assert attributes["deployment.environment.name"] == "ci"
    assert attributes["service.version"]


def test_privacy_settings_win_over_the_environment(instrument, monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("GENAI_ENABLE_CONTENT_CAPTURE", "true")
    monkeypatch.setenv("TRACEVERDE_TELEMETRY", "true")

    configure_telemetry(Settings())

    assert os.environ["GENAI_ENABLE_CONTENT_CAPTURE"] == "false"
    assert os.environ["TRACEVERDE_TELEMETRY"] == "false"


@pytest.fixture
def exported_logs():
    """Our logger's records, exported in memory; the handler is removed afterwards."""
    app_logger = logging.getLogger(APP_LOGGER)
    saved = app_logger.handlers[:]
    exporter = InMemoryLogRecordExporter()
    provider = attach_log_handler(exporter, Resource.create({"service.name": "test"}))

    def finished():
        provider.force_flush()
        return [data.log_record for data in exporter.get_finished_logs()]

    yield finished
    app_logger.handlers[:] = saved
    provider.shutdown()


def test_log_record_carries_trace_and_span_of_current_span(exported_logs):
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("triage") as span:
        logging.getLogger("ticket_classifier.runner").warning("calling model")

    (record,) = exported_logs()
    assert record.body == "calling model"
    assert record.trace_id == span.get_span_context().trace_id
    assert record.span_id == span.get_span_context().span_id


def test_extra_fields_become_log_attributes(exported_logs):
    logging.getLogger("ticket_classifier.runner").warning(
        "paused", extra={"ticket_id": "T-3"}
    )

    (record,) = exported_logs()
    assert record.attributes["ticket_id"] == "T-3"


def test_other_libraries_logs_are_not_exported(exported_logs):
    logging.getLogger("opentelemetry.exporter").warning("export failed")
    logging.getLogger("anthropic").warning("retrying")

    assert exported_logs() == []


def test_attaching_twice_keeps_one_handler(exported_logs):
    attach_log_handler(InMemoryLogRecordExporter(), Resource.create({}))
    attach_log_handler(InMemoryLogRecordExporter(), Resource.create({}))

    handlers = logging.getLogger(APP_LOGGER).handlers
    assert [h.get_name() for h in handlers].count(OTEL_HANDLER_NAME) == 1
