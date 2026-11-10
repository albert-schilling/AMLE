import argparse
import json
import logging
from pathlib import Path

from pydantic import TypeAdapter

from .classifier import ClassificationError, classify, create_client
from .config import get_settings
from .models import Ticket

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
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args = parse_args(argv)
    tickets_path = args.tickets or get_settings().tickets_path
    tickets = TypeAdapter(list[Ticket]).validate_json(
        tickets_path.read_text(encoding="utf-8")
    )

    logger.info("Loaded %d tickets from %s", len(tickets), tickets_path)

    client = create_client()
    results = []
    failures = 0
    for ticket in tickets:
        try:
            result = classify(ticket, client=client)
        except ClassificationError as error:
            failures += 1
            logger.error("Ticket %s failed: %s", ticket.id, error)
            continue

        logger.info("Ticket %s -> %s / %s", ticket.id, result.category, result.priority)
        results.append(
            {
                "ticket_id": ticket.id,
                "customer_id": ticket.customer_id,
                "category": result.category,
                "priority": result.priority,
            }
        )

    results_path = get_settings().results_path
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info(
        "Classified %d/%d tickets, results in %s",
        len(results),
        len(tickets),
        results_path,
    )

    return 1 if failures else 0
