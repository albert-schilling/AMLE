"""Behavior evals: run real tickets against the model and check what the agent did.

Unit tests cannot show that the model follows the prompt, so this runs a few tickets
several times and prints how often each check passed. It calls the real API and costs
money; results vary between runs. Run it with ``make eval`` or
``uv run python -m ticket_classifier.evals --runs 5``.

The checks read the trace log lines of a run (``Action: ...`` / ``Observation: ...``).
"""

import argparse
import logging
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .classifier import classify, create_client, upload_log
from .config import get_settings
from .storage import load_tickets
from .trace import trace_logger

Check = Callable[[list[str]], bool]


def called(lines: list[str], tool: str, containing: str = "") -> bool:
    return any(f"Action: {tool}(" in line and containing in line for line in lines)


def count_calls(lines: list[str], tool: str) -> int:
    return sum(f"Action: {tool}(" in line for line in lines)


def observed(lines: list[str], text: str) -> bool:
    return any("Observation:" in line and text in line for line in lines)


def code_printed_count(lines: list[str], expected: int) -> bool:
    """Some code run printed the expected number on a line of its own."""
    pattern = re.compile(rf"(?mi)(^|exit \d+:)\s*(count\w*\s*[:=]\s*)?{expected}\s*$")
    return any(
        "Observation: code execution" in line and pattern.search(line) for line in lines
    )


@dataclass
class Case:
    ticket_id: str
    checks: dict[str, Check]


CASES = [
    Case(
        "T-2001",
        {"fetched the status page": lambda t: called(t, "web_fetch", "status.mollie")},
    ),
    Case(
        "T-2002",
        {
            "ran code": lambda t: called(t, "bash_code_execution"),
            "code printed 5": lambda t: code_printed_count(t, 5),
            "at most 3 code calls": lambda t: (
                count_calls(t, "bash_code_execution") <= 3
            ),
        },
    ),
    Case(
        "T-2004",
        {
            "fetched payments": lambda t: called(t, "web_fetch", "payments.json"),
            "tool found the duplicate": lambda t: observed(t, "INV-2026-1101"),
        },
    ),
    Case(
        "T-2005",
        {
            "fetched payments": lambda t: called(t, "web_fetch", "payments.json"),
            "tool found no duplicate": lambda t: observed(
                t, "No duplicate charges found"
            ),
        },
    ),
]


class TraceCollector(logging.Handler):
    """Collects trace records of the current thread, so parallel runs stay apart."""

    def __init__(self) -> None:
        super().__init__()
        self.local = threading.local()

    def emit(self, record: logging.LogRecord) -> None:
        lines = getattr(self.local, "lines", None)
        if lines is not None:
            lines.append(record.getMessage())


def run_once(ticket, client, log_file_id, collector) -> list[str]:
    collector.local.lines = []
    try:
        classify(ticket, client, lambda reason: False, log_file_id)
    except Exception as error:  # an API error counts as a failed run
        collector.local.lines.append(f"ERROR {error}")
    return collector.local.lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run behavior evals (costs money).")
    parser.add_argument("--runs", type=int, default=5, help="runs per ticket")
    args = parser.parse_args(argv)

    settings = get_settings()
    tickets = {ticket.id: ticket for ticket in load_tickets(settings.tickets_path)}
    client = create_client()
    log_file_id = upload_log(client, settings.log_path)

    collector = TraceCollector()
    trace_logger.addHandler(collector)
    trace_logger.propagate = False  # keep the evals output readable
    trace_logger.setLevel(logging.INFO)

    print(f"model={settings.model} fetch={settings.fetch_backend} runs={args.runs}")
    with ThreadPoolExecutor() as pool:
        for case in CASES:
            futures = [
                pool.submit(
                    run_once, tickets[case.ticket_id], client, log_file_id, collector
                )
                for _ in range(args.runs)
            ]
            traces = [future.result() for future in futures]
            print(f"\n{case.ticket_id}")
            for name, check in case.checks.items():
                passed = sum(check(trace) for trace in traces)
                print(f"  {passed:>2}/{args.runs}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
