from opentelemetry import trace
from pydantic import ValidationError

from . import commands
from .args import ResumeArgs, RunArgs, parse_args
from .config import Settings, get_settings
from .logging_config import configure_logging
from .runner import NotPausedError
from .storage import load_tickets
from .telemetry import configure_telemetry, get_loggers

logger, safe_log = get_loggers(__name__)
# A no-op tracer while telemetry is off; becomes real once a provider is set.
tracer = trace.get_tracer(__name__)


def main(argv: list[str] | None = None) -> int:
    """Exit code: 0 ok, 1 some tickets failed, 2 bad input."""
    args = parse_args(argv)  # first, so --help works without settings

    settings = get_settings()
    configure_logging(settings)
    configure_telemetry(settings)  # before the first Anthropic client is created

    # Root span of the command: every span and log line of this process is in it.
    match args:
        case RunArgs():
            with tracer.start_as_current_span("ticket-classifier run"):
                return handle_run(args, settings)
        case ResumeArgs():
            with tracer.start_as_current_span("ticket-classifier resume"):
                return handle_resume(args, settings)


def handle_run(args: RunArgs, settings: Settings) -> int:
    """Load the tickets and run them all; 2 if they cannot be loaded or no API key."""
    tickets_path = args.tickets or settings.tickets_path
    try:
        tickets = load_tickets(tickets_path)
    except (OSError, ValidationError) as error:
        # A validation error can quote the ticket text.
        safe_log.error("Cannot load tickets: %s", type(error).__name__)
        logger.error("Tickets file %s: %s", tickets_path, error)
        return 2
    safe_log.info("Loaded %d tickets", len(tickets))
    logger.info("Tickets file: %s", tickets_path)

    try:
        batch = commands.run(tickets, settings)
    except commands.MissingApiKeyError as error:
        safe_log.error("%s", error)
        return 2
    return 1 if batch.failed else 0


def handle_resume(args: ResumeArgs, settings: Settings) -> int:
    """Answer one paused ticket; 2 if it has no paused run."""
    try:
        commands.resume(args.ticket_id, args.answer, settings)
    except NotPausedError as error:
        safe_log.error("%s", error)
        return 2
    return 0
