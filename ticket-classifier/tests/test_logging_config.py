import logging

import pytest

from ticket_classifier.config import Settings
from ticket_classifier.logging_config import QUIET_LOGGERS, configure_logging


@pytest.fixture(autouse=True)
def _restore_loggers():
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    yield
    root.handlers[:], root.level = saved


def ours(log):
    return [h for h in log.handlers if h.get_name() == "ticket_classifier"]


def flush():
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_log_file_receives_records(tmp_path, monkeypatch):
    log_file = tmp_path / "logs" / "run.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))
    configure_logging(Settings())

    logging.getLogger("ticket_classifier.cli").info("Loaded 1 tickets")
    flush()

    assert "Loaded 1 tickets" in log_file.read_text()


def test_configure_logging_twice_adds_no_duplicate_handlers():
    configure_logging(Settings())
    configure_logging(Settings())

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

    logging.getLogger("ticket_classifier").info("first line\n\nsecond line")
    flush()

    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    assert "first line\\n\\nsecond line" in lines[0]
