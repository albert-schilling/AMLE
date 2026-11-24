import io
import json
import logging
import os

import pytest
from helpers import HIGH
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs.export import (
    ConsoleLogRecordExporter,
    InMemoryLogRecordExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from ticket_classifier.cli import main
from ticket_classifier.client import get_client
from ticket_classifier.config import Settings
from ticket_classifier.models import KnowledgePassage
from ticket_classifier.telemetry import (
    APP_LOGGER,
    EXPORT_LOG,
    OTEL_HANDLER_NAME,
    TelemetrySetupError,
    attach_log_handler,
    configure_telemetry,
    get_loggers,
    log_exporter,
    ticket_span,
)


@pytest.fixture
def instrument(mocker):
    """The TraceVerde call, mocked: no global OTel providers or handlers in tests."""
    mocker.patch.dict(os.environ)  # restores env vars written by the code
    mocker.patch(
        "opentelemetry.trace.get_tracer_provider", return_value=TracerProvider()
    )
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
        logging.getLogger("ticket_classifier.runner").warning(
            "calling model", extra=EXPORT_LOG
        )

    (record,) = exported_logs()
    assert record.body == "calling model"
    assert record.trace_id == span.get_span_context().trace_id
    assert record.span_id == span.get_span_context().span_id


def test_extra_fields_become_log_attributes(exported_logs):
    logging.getLogger("ticket_classifier.runner").warning(
        "paused", extra={"ticket_id": "T-3", **EXPORT_LOG}
    )

    (record,) = exported_logs()
    assert record.attributes["ticket_id"] == "T-3"


def test_other_libraries_logs_are_not_exported(exported_logs):
    logging.getLogger("opentelemetry.exporter").warning(
        "export failed", extra=EXPORT_LOG
    )
    logging.getLogger("anthropic").warning("retrying", extra=EXPORT_LOG)

    assert exported_logs() == []


def test_attaching_twice_keeps_one_handler(exported_logs):
    attach_log_handler(InMemoryLogRecordExporter(), Resource.create({}))
    attach_log_handler(InMemoryLogRecordExporter(), Resource.create({}))

    handlers = logging.getLogger(APP_LOGGER).handlers
    assert [h.get_name() for h in handlers].count(OTEL_HANDLER_NAME) == 1


def test_log_inside_ticket_span_gets_ticket_ids(exported_logs):
    log = logging.getLogger("ticket_classifier.runner")
    with ticket_span("T-3", "run"):
        log.warning("inside", extra=EXPORT_LOG)
    log.warning("outside", extra=EXPORT_LOG)

    inside, outside = exported_logs()
    assert inside.attributes["ticket_id"] == "T-3"
    assert inside.attributes["thread_id"] == "T-3"
    assert "ticket_id" not in outside.attributes


def test_ticket_ids_are_cleared_after_an_error(exported_logs):
    log = logging.getLogger("ticket_classifier.runner")
    with pytest.raises(ValueError), ticket_span("T-3", "run"):
        raise ValueError("boom")
    log.warning("after", extra=EXPORT_LOG)

    (record,) = exported_logs()
    assert "ticket_id" not in record.attributes


def test_debug_lines_are_not_exported(exported_logs):
    logging.getLogger(APP_LOGGER).setLevel(logging.DEBUG)
    logging.getLogger("ticket_classifier.runner").debug("whole state", extra=EXPORT_LOG)

    assert exported_logs() == []


def test_unmarked_line_is_not_exported_but_still_logged(exported_logs, caplog):
    with caplog.at_level(logging.INFO):
        logging.getLogger("ticket_classifier.runner").info("secret text")

    assert exported_logs() == []
    assert "secret text" in caplog.text


def test_run_and_resume_export_no_ticket_customer_or_policy_text(
    model, knowledge, write_tickets, exported_logs, monkeypatch
):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    knowledge.passages = [
        KnowledgePassage(source="refunds.md", ordinal=1, text="private policy", score=1)
    ]
    model.outcomes["private ticket text"] = HIGH
    tickets = write_tickets([{"id": "T-1", "text": "private ticket text"}])

    main(["run", str(tickets)])
    main(["resume", "T-1", "--approve", "--note", "private reviewer note"])

    bodies = " ".join(str(record.body) for record in exported_logs())
    assert "T-1" in bodies
    assert "refunds.md#1" in bodies  # the citation is safe, the text is not
    for private in (
        "private ticket text",
        "private reviewer note",
        "private policy",
        "alice@",
    ):
        assert private not in bodies


def test_client_sends_no_trace_headers_to_anthropic():
    get_client.cache_clear()

    options = get_client().open_telemetry
    assert options["propagation"] is False
    assert options["traces"]["content_mode"] == "metadata_only"

    get_client.cache_clear()


def test_malformed_customer_is_not_exported(
    model, write_tickets, exported_logs, customers_file
):
    customers_file.write_text(
        json.dumps({"1001": {"id": "1001", "email": "private@example.com"}})
    )
    tickets = write_tickets([{"id": "T-1", "customer_id": "1001", "text": "x"}])

    main(["run", str(tickets)])

    records = exported_logs()
    exported = " ".join(f"{r.body} {dict(r.attributes)}" for r in records)
    assert "continues without customer data" in exported
    assert "private@example.com" not in exported


def test_logs_go_to_console_without_endpoint(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    assert isinstance(log_exporter(Settings()), ConsoleLogRecordExporter)


def test_logs_go_to_collector_with_endpoint():
    assert isinstance(log_exporter(Settings()), OTLPLogExporter)


def test_logs_use_the_same_resource_as_traces(instrument, monkeypatch, mocker):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    provider = TracerProvider()
    mocker.patch("opentelemetry.trace.get_tracer_provider", return_value=provider)
    attach = mocker.patch("ticket_classifier.telemetry.attach_log_handler")

    configure_telemetry(Settings())

    assert attach.call_args.args[1] is provider.resource


def test_disabled_telemetry_attaches_no_log_handler(model, write_tickets):
    main(["run", str(write_tickets([{"id": "T-1", "text": "calm"}]))])

    handlers = logging.getLogger(APP_LOGGER).handlers
    assert OTEL_HANDLER_NAME not in [handler.get_name() for handler in handlers]


def test_run_and_resume_logs_share_ticket_id_across_two_traces(
    model, write_tickets, exported_logs, finished_spans
):
    model.outcomes["urgent"] = HIGH
    main(["run", str(write_tickets([{"id": "T-1", "text": "urgent"}]))])
    main(["resume", "T-1", "--approve", "--note", "ok"])

    records = [r for r in exported_logs() if r.attributes.get("ticket_id") == "T-1"]
    assert len({record.trace_id for record in records}) == 2


def test_marker_is_not_exported_as_attribute(exported_logs):
    logging.getLogger("ticket_classifier.runner").warning("safe", extra=EXPORT_LOG)

    (record,) = exported_logs()
    assert "export_log" not in record.attributes


@pytest.mark.parametrize(
    "name",
    [
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_HEADERS",
    ],
)
def test_otlp_overrides_are_removed(instrument, monkeypatch, name):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv(name, "https://elsewhere.example")

    configure_telemetry(Settings())

    assert name not in os.environ


def test_standard_capture_variable_cannot_turn_content_on(instrument, monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY"
    )

    configure_telemetry(Settings())

    assert (
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "NO_CONTENT"
    )


def test_failed_setup_raises_a_clear_error(instrument, monkeypatch, mocker):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    mocker.patch("opentelemetry.trace.get_tracer_provider", return_value=object())

    with pytest.raises(TelemetrySetupError, match="could not start"):
        configure_telemetry(Settings())


def test_only_the_safe_logger_line_is_exported(exported_logs, caplog):
    logger, safe_log = get_loggers("ticket_classifier.runner")
    with caplog.at_level(logging.INFO):
        logger.info("private line")
        safe_log.info("Ticket %s started", "T-1")

    (record,) = exported_logs()
    assert record.body == "Ticket T-1 started"
    assert "export_log" not in record.attributes
    assert "Ticket T-1 started" in caplog.text


@pytest.fixture
def console():
    """What a handler on the root logger, like the app's console, receives."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    root = logging.getLogger()
    root.addHandler(handler)
    yield stream
    root.removeHandler(handler)


def test_exported_lines_hold_no_file_paths(
    model, write_tickets, exported_logs, tmp_path
):
    model.outcomes["urgent"] = HIGH
    tickets = write_tickets([{"id": "T-1", "text": "urgent"}])
    main(["run", str(tickets)])
    main(["resume", "T-1", "--approve", "--note", "ok"])
    main(["run", str(tmp_path / "missing.json")])

    bodies = " ".join(str(record.body) for record in exported_logs())
    assert "Ticket T-1 done" in bodies
    assert "Cannot load tickets: FileNotFoundError" in bodies
    for path_part in (str(tmp_path), ".json", "output/"):
        assert path_part not in bodies


def test_failure_exports_its_type_and_keeps_detail_on_console(
    model, write_tickets, exported_logs, console
):
    model.outcomes["broken"] = None

    main(["run", str(write_tickets([{"id": "T-1", "text": "broken"}]))])

    bodies = " ".join(str(record.body) for record in exported_logs())
    assert "Ticket T-1 failed: TriageError" in bodies
    assert "stop_reason" not in bodies
    assert "stop_reason" in console.getvalue()
