import logging

from .config import Settings

HANDLER_NAME = "ticket_classifier"  # marks our handlers, so a second call can find them
# No request dumps on DEBUG. The Anthropic SDK sends through httpx2 / httpcore2.
QUIET_LOGGERS = ("anthropic", "httpx", "httpcore", "httpx2", "httpcore2")
FULL_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class SingleLineFormatter(logging.Formatter):
    """One record per line, also for tracebacks: newlines become a literal ``\\n``."""

    def format(self, record: logging.LogRecord) -> str:
        return super().format(record).replace("\r", "").replace("\n", "\\n")


def configure_logging(settings: Settings) -> None:
    """Log to the console, and also to ``log_file`` if it is set.

    Safe to call again (``main()`` runs many times in tests): our handlers from an
    earlier call are replaced, not added twice.
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
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
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
        file_handler.setFormatter(SingleLineFormatter(FULL_FORMAT))
        file_handler.set_name(HANDLER_NAME)
        root.addHandler(file_handler)
