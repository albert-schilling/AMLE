import logging

import pytest

from ticket_classifier.config import Settings
from ticket_classifier.logging_config import configure_logging
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

    assert len(trace_logger.handlers) == 1
    ours = [
        h for h in logging.getLogger().handlers if h.get_name() == "ticket_classifier"
    ]
    assert len(ours) == 1
