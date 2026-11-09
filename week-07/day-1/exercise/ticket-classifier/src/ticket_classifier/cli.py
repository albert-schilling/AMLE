import argparse
import logging
from pathlib import Path

from pydantic import TypeAdapter

from .classifier import ClassificationError, classify, create_client
from .models import Ticket

DEFAULT_TICKETS = Path("sample_tickets.json")

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
    args = parse_args(argv)
    tickets = TypeAdapter(list[Ticket]).validate_json(
        args.tickets.read_text(encoding="utf-8")
    )

    client = create_client()
    failures = 0
    for ticket in tickets:
        try:
            result = classify(ticket.text, client=client)
        except ClassificationError as error:
            failures += 1
            logger.error("%s: %s", ticket.id, error)
            continue
        print(f"{ticket.id}: {ticket.text[:50]} -> {result.category} {result.priority}")
    return 1 if failures else 0
