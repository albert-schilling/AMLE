import logging

import pytest

from ticket_classifier.config import Settings
from ticket_classifier.logging_config import QUIET_LOGGERS, configure_logging
from ticket_classifier.trace import TRACE_LOGGER_NAME, trace_logger


@pytest.fixture(autouse=True)
def _restore_loggers():
    root = logging.getLogger()
    saved = (root.handlers[:], root.level, trace_logger.propagate)
    yield
    root.handlers[:], root.level = saved[0], saved[1]
    trace_logger.handlers.clear()
    trace_logger.propagate = saved[2]


def ours(log):
    return [h for h in log.handlers if h.get_name() == "ticket_classifier"]


def test_trace_goes_to_own_handler_not_root():
    configure_logging(Settings())

    trace = logging.getLogger(TRACE_LOGGER_NAME)
    assert trace.propagate is False
    assert len(ours(trace)) == 1


def test_log_file_receives_trace_and_diagnostics(tmp_path, monkeypatch):
    log_file = tmp_path / "logs" / "run.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))
    configure_logging(Settings())

    trace_logger.info("[T-1] Final: ok")
    logging.getLogger("ticket_classifier.cli").info("Loaded 1 tickets")
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_file.read_text()
    assert "[T-1] Final: ok" in content
    assert "Loaded 1 tickets" in content


def test_configure_logging_twice_adds_no_duplicate_handlers():
    configure_logging(Settings())
    configure_logging(Settings())

    assert len(ours(trace_logger)) == 1
    assert len(ours(logging.getLogger())) == 1


def test_sdk_and_http_loggers_stay_at_info_even_on_debug(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging(Settings())

    assert logging.getLogger().level == logging.DEBUG
    for name in QUIET_LOGGERS:
        assert logging.getLogger(name).level == logging.INFO


def test_log_file_keeps_one_record_per_line(tmp_path, monkeypatch):
    log_file = tmp_path / "run.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))
    configure_logging(Settings())

    trace_logger.info("[T-1] step 1 Thinking: first line\n\n1. second line")
    for handler in logging.getLogger().handlers:
        handler.flush()

    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    assert "[T-1] step 1 Thinking: first line\\n\\n1. second line" in lines[0]


def test_console_keeps_real_newlines():
    configure_logging(Settings())

    console = next(
        h for h in trace_logger.handlers if h.get_name() == "ticket_classifier"
    )
    record = logging.LogRecord("t", logging.INFO, "", 0, "a\nb", None, None)
    assert console.format(record) == "a\nb"
