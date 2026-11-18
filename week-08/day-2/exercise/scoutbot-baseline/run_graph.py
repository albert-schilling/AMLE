"""Entry point for Week 8 Day 1: run the sample tickets through the graph, printing the state
after each node so you can watch it fill up.

Deliberately a separate file from `main.py`, which still runs Week 7's ReAct loop exactly as it
did. Today adds a second path through the same repo rather than replacing the first one, so both
are runnable side by side and the difference is something you can see rather than take on trust.

`stream(..., stream_mode=["updates", "values"])` is what makes the day's point visible, in a
single run: an `updates` chunk is one node's return value (only the fields that node changed,
keyed by node name), and the `values` chunk right after it is the whole state once that update
has been merged in. Watching the two together is how the reducer stops being abstract - `notes`
grows across nodes, while `customer` and `triage` are simply replaced by whoever wrote last.
Streaming both modes at once also means one model call per ticket, not one per stream mode.

Checkpoints go to checkpoints.db. A ticket with an unfinished saved run is resumed, not
restarted. `--crash` kills the process once a ticket's triage is saved, so the next plain run
has something to resume. Delete checkpoints.db to start clean.

Usage:
    python run_graph.py [--crash]
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from scoutbot import build_ticket_graph, initial_state

load_dotenv()

TICKETS_PATH = Path(__file__).parent / "sample_tickets.json"
CHECKPOINT_DB = Path(__file__).parent / "checkpoints.db"
WATCHED_FIELDS = ("customer", "triage", "notes")


def _print_fields(indent: str, data: dict, fields=WATCHED_FIELDS) -> None:
    for field in fields:
        if field in data:
            print(f"{indent}{field}: {json.dumps(data[field])}")


def main(crash: bool = False):
    # Compiled once and reused for every ticket - a compiled graph is a reusable object, not a
    # per-run one.
    connection = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    graph = build_ticket_graph(checkpointer=SqliteSaver(connection))
    tickets = json.loads(TICKETS_PATH.read_text())

    for ticket in tickets:
        print(f"=== {ticket['id']}: {ticket['text'][:60]}... ===")

        # One thread per ticket: the thread_id is the key its checkpoints are stored under.
        config = {"configurable": {"thread_id": ticket["id"]}}

        # An unfinished run is saved for this ticket: continue it with None as input. Passing
        # a state again would start a new run instead.
        if graph.get_state(config).next:
            print("  unfinished run found, resuming")
            state = None
        else:
            state = initial_state(ticket["text"], ticket["customer_id"], ticket["id"])

        first_snapshot = True
        for mode, chunk in graph.stream(
            state, config, stream_mode=["updates", "values"], durability="sync"
        ):
            if mode == "updates":
                for node_name, update in chunk.items():
                    print(f"  node {node_name!r} returned only:")
                    _print_fields("      ", update)
            else:
                print(f"  {'starting state:' if first_snapshot else 'state is now:'}")
                _print_fields("      ", chunk)
                first_snapshot = False
                if crash and chunk["triage"] and not chunk["outcome"]:
                    print("  triage saved, killing the process", flush=True)
                    os._exit(1)

        # Retrieve and print the saved state from the checkpointer.
        snapshot = graph.get_state(config)
        print(f"  saved: next={snapshot.next}, outcome={snapshot.values['outcome']!r}")
        print()


if __name__ == "__main__":
    main(crash="--crash" in sys.argv)
