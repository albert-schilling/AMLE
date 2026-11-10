import argparse
import logging
from pathlib import Path

from pydantic import ValidationError

from .approval import console_approval
from .batch import classify_all
from .classifier import create_client
from .config import get_settings
from .logging_config import configure_logging
from .storage import load_tickets, save_results

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ticket-classifier", description="Classify support tickets with Claude."
    )
    parser.add_argument(
        "tickets",
        nargs="?",
        type=Path,
        default=None,
        help="JSON file with tickets (default: TICKETS_PATH setting)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings)

    args = parse_args(argv)
    tickets_path = args.tickets or settings.tickets_path
    try:
        tickets = load_tickets(tickets_path)
    except (OSError, ValidationError) as error:
        logger.error("Cannot load tickets from %s: %s", tickets_path, error)
        return 2

    logger.info("Loaded %d tickets from %s", len(tickets), tickets_path)

    batch = classify_all(tickets, create_client(), console_approval)
    save_results(batch.classified, settings.results_path)
    logger.info(
        "Classified %d/%d tickets, results in %s",
        len(batch.classified),
        len(tickets),
        settings.results_path,
    )

    return 1 if batch.failed else 0
