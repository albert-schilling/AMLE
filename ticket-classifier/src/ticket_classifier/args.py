"""Command-line arguments, parsed into one typed object per subcommand."""

import argparse
from dataclasses import dataclass
from pathlib import Path

from .models import HumanAnswer


@dataclass(frozen=True)
class RunArgs:
    tickets: Path | None  # None: use the TICKETS_PATH setting


@dataclass(frozen=True)
class ResumeArgs:
    ticket_id: str
    answer: HumanAnswer


@dataclass(frozen=True)
class KbIndexArgs:
    """No options: folder, model and chunk setting come from the settings."""


def parse_args(argv: list[str] | None = None) -> RunArgs | ResumeArgs | KbIndexArgs:
    namespace = build_parser().parse_args(argv)
    if namespace.command == "run":
        return RunArgs(tickets=namespace.tickets)
    if namespace.command == "kb-index":
        return KbIndexArgs()
    return ResumeArgs(
        ticket_id=namespace.ticket_id,
        answer=HumanAnswer(approved=namespace.approved, note=namespace.note),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket-classifier", description="Classify support tickets with Claude."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser(
        "run", help="classify tickets; high-priority ones pause for a human"
    )
    run.add_argument(
        "tickets",
        nargs="?",
        type=Path,
        default=None,
        help="JSON file with tickets (default: TICKETS_PATH setting)",
    )

    resume = subcommands.add_parser(
        "resume", help="answer a paused ticket and finish its run"
    )
    resume.add_argument("ticket_id", help="id of the paused ticket")
    decision = resume.add_mutually_exclusive_group(required=True)
    decision.add_argument(
        "--approve",
        dest="approved",
        action="store_true",
        help="a human takes over the ticket",
    )
    decision.add_argument(
        "--decline",
        dest="approved",
        action="store_false",
        help="no human takes over the ticket",
    )
    resume.add_argument("--note", default="", help="the human's note on the decision")

    subcommands.add_parser(
        "kb-index",
        help="embed the knowledge base into PostgreSQL; skipped if it is unchanged",
    )

    return parser
