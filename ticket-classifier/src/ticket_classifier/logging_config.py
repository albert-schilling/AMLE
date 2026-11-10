import logging
from pathlib import Path

from .config import Settings
from .trace import TRACE_LOGGER_NAME

HANDLER_NAME = "ticket_classifier"
FULL_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(settings: Settings) -> None:
    """Console: diagnostics with full format, trace in plain format.

    If ``log_file`` is set, both also go to that file with timestamps.
    """
    root = logging.getLogger()
    trace = logging.getLogger(TRACE_LOGGER_NAME)
    for log in (root, trace):  # idempotent: drop handlers from an earlier call
        for handler in log.handlers[:]:
            if handler.get_name() == HANDLER_NAME:
                log.removeHandler(handler)
                handler.close()

    root.setLevel(settings.log_level)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(FULL_FORMAT))
    console.set_name(HANDLER_NAME)
    root.addHandler(console)

    trace.setLevel(settings.log_level)
    trace.propagate = False  # own handlers, so the root console doesn't repeat it
    trace_console = logging.StreamHandler()
    trace_console.setFormatter(logging.Formatter("%(message)s"))
    trace_console.set_name(HANDLER_NAME)
    trace.addHandler(trace_console)

    if settings.log_file is not None:
        add_file_handler(settings.log_file, root, trace)


def add_file_handler(path: Path, *loggers: logging.Logger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(FULL_FORMAT))
    handler.set_name(HANDLER_NAME)
    for log in loggers:
        log.addHandler(handler)
