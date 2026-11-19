import argparse
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from anthropic import APIError
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import ValidationError

from .approval import console_approval
from .batch import classify_all
from .client import get_client, upload_log
from .config import get_settings
from .graph import build_workflow, write_mermaid
from .logging_config import configure_logging
from .models import Customer, Escalated, NotEscalated, Ticket, TicketClassification
from .storage import load_tickets, merge_results, save_results

logger = logging.getLogger(__name__)

# State types saved in checkpoints; only these (and safe built-ins) load back.
CHECKPOINT_TYPES = [Customer, Escalated, NotEscalated, Ticket, TicketClassification]
CHECKPOINT_SERDE = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)


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
    parser.add_argument(
        "--resume",
        metavar="TICKET_ID",
        help="answer the paused run of this ticket, then finish it",
    )
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument(
        "--approve", action="store_true", help="a human takes over the ticket"
    )
    decision.add_argument(
        "--decline", action="store_true", help="no human takes over the ticket"
    )
    parser.add_argument("--note", default="", help="the human's note on the decision")
    args = parser.parse_args(argv)
    if args.resume and not (args.approve or args.decline):
        parser.error("--resume needs --approve or --decline")
    if not args.resume and (args.approve or args.decline or args.note):
        parser.error("--approve, --decline and --note need --resume")
    return args


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

    answers = {}
    if args.resume:
        tickets = [ticket for ticket in tickets if ticket.id == args.resume]
        if not tickets:
            logger.error("Ticket %s is not in %s", args.resume, tickets_path)
            return 2
        answers[args.resume] = {"approved": args.approve, "note": args.note}

    log_file_id = None
    if not args.resume and settings.log_path.exists():  # a resume needs no model call
        client = get_client()
        try:
            log_file_id = upload_log(client, settings.log_path)
        except APIError as error:
            logger.error(
                "Cannot upload %s, continuing without it: %s", settings.log_path, error
            )

    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(
        sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    ) as connection:
        workflow = build_workflow(SqliteSaver(connection, serde=CHECKPOINT_SERDE))
        write_mermaid(workflow, settings.graph_path)
        batch = classify_all(
            tickets,
            console_approval,
            log_file_id,
            workflow=workflow,
            answers=answers,
        )
    if args.resume:
        merge_results(batch.classified, settings.results_path)
    else:
        save_results(batch.classified, settings.results_path)
    logger.info(
        "Classified %d/%d tickets, results in %s",
        len(batch.classified),
        len(tickets),
        settings.results_path,
    )
    for ticket_id in batch.paused:
        logger.info(
            "Ticket %s waits for a human. Answer with: "
            "ticket-classifier --resume %s --approve|--decline --note TEXT",
            ticket_id,
            ticket_id,
        )

    return 1 if batch.failed else 0
