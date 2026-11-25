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


@dataclass(frozen=True)
class KbEvalArgs:
    """Every size with every overlap; raises ``ValueError`` if none fits."""

    sizes: list[int]
    overlaps: list[int]
    thresholds: list[float]  # minimum scores to compare

    def __post_init__(self) -> None:
        if not self.chunk_settings:
            raise ValueError("kb-eval: no overlap is smaller than any size")

    @property
    def chunk_settings(self) -> list[tuple[int, int]]:
        """(size, overlap) pairs; an overlap not below the size is skipped."""
        return [
            (size, overlap)
            for size in self.sizes
            for overlap in self.overlaps
            if overlap < size
        ]


Args = RunArgs | ResumeArgs | KbIndexArgs | KbEvalArgs


def parse_args(argv: list[str] | None = None) -> Args:
    parser = build_parser()
    namespace = parser.parse_args(argv)

    try:
        match namespace.command:
            case "run":
                return RunArgs(tickets=namespace.tickets)
            case "resume":
                return ResumeArgs(
                    ticket_id=namespace.ticket_id,
                    answer=HumanAnswer(
                        approved=namespace.approved, note=namespace.note
                    ),
                )
            case "kb-index":
                return KbIndexArgs()
            case "kb-eval":
                return KbEvalArgs(
                    sizes=namespace.sizes,
                    overlaps=namespace.overlaps,
                    thresholds=namespace.thresholds,
                )
    except ValueError as error:
        parser.error(str(error))  # exits with code 2, like other bad arguments

    # A subcommand in build_parser without a case above.
    raise AssertionError(f"unhandled command: {namespace.command}")


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

    kb_eval = subcommands.add_parser(
        "kb-eval", help="compare chunk settings on the labelled questions"
    )
    kb_eval.add_argument(
        "--sizes",
        nargs="+",
        type=positive_int,
        default=[30, 60, 120],
        help="chunk sizes in words",
    )
    kb_eval.add_argument(
        "--overlaps",
        nargs="+",
        type=non_negative_int,
        default=[0, 10, 20],
        help="overlaps in words; skipped where not smaller than the size",
    )
    kb_eval.add_argument(
        "--thresholds",
        nargs="+",
        type=cosine,
        default=[0.5, 0.55, 0.6, 0.65, 0.7],
        help="minimum scores to compare on the configured chunk setting",
    )

    return parser


def positive_int(text: str) -> int:
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be positive: {value}")
    return value


def non_negative_int(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return value


def cosine(text: str) -> float:
    value = float(text)
    if not -1 <= value <= 1:
        raise argparse.ArgumentTypeError(f"must be between -1 and 1: {value}")
    return value
