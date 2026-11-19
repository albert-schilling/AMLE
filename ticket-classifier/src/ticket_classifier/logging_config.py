import logging
from pathlib import Path

from .config import Settings

HANDLER_NAME = "ticket_classifier"
QUIET_LOGGERS = ("anthropic", "httpx", "httpcore")
FULL_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class SingleLineFormatter(logging.Formatter):
    """One record per line: newlines become a literal backslash-n (for log files)."""

    def format(self, record: logging.LogRecord) -> str:
        return super().format(record).replace("\r", "").replace("\n", "\\n")


def configure_logging(settings: Settings) -> None:
    """Log to the console, and also to ``log_file`` if it is set."""
    root = logging.getLogger()
    for handler in root.handlers[:]:  # idempotent: drop handlers from an earlier call
        if handler.get_name() == HANDLER_NAME:
            root.removeHandler(handler)
            handler.close()

    root.setLevel(settings.log_level)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(FULL_FORMAT))
    console.set_name(HANDLER_NAME)
    root.addHandler(console)

    if settings.log_file is not None:
        add_file_handler(settings.log_file, root)


def add_file_handler(path: Path, logger: logging.Logger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(SingleLineFormatter(FULL_FORMAT))
    handler.set_name(HANDLER_NAME)
    logger.addHandler(handler)
