import argparse
import json
import logging
from pathlib import Path

from pydantic import TypeAdapter

from .classifier import ClassificationError, classify, create_client
from .config import get_settings
from .models import Ticket

DEFAULT_TICKETS = Path("fixtures/tickets.json")

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ticket-classifier", description="Classify support tickets with Claude."
    )
    parser.add_argument(
        "tickets",
        nargs="?",
        type=Path,
        default=DEFAULT_TICKETS,
        help=f"JSON file with tickets (default: {DEFAULT_TICKETS})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args = parse_args(argv)
    tickets = TypeAdapter(list[Ticket]).validate_json(
        args.tickets.read_text(encoding="utf-8")
    )

    client = create_client()
    failures = 0
    for ticket in tickets:
        try:
            result = classify(ticket, client=client)
        except ClassificationError as error:
            failures += 1
            logger.error("%s: %s", ticket.id, error)
            continue

        # Write results in fixtures/results.json
        results_path = Path("fixtures/results.json")
        if results_path.exists():
            results = json.loads(results_path.read_text(encoding="utf-8"))
        else:
            results = []
        results.append(
            {
                "ticket_id": ticket.id,
                "customer_id": ticket.customer_id,
                "category": result.category,
                "priority": result.priority,
            }
        )
        results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    return 1 if failures else 0
