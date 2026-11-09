"""The day's centrepiece: one run, two processes.

Friday, 4:50pm. A refund ticket comes in, triage marks it high priority, and it routes to
`escalate` to wait for a person. Then the box restarts.

    python run_resume.py --crash    # Friday: the process dies inside the escalate node
    python run_resume.py            # Saturday: a NEW process finishes the same run

The first invocation really does die, via `os._exit(1)`: no exception, no cleanup, nothing given a
chance to save anything on the way out. That is the point. Whatever comes back on Saturday came
back because it was already durable, not because this script was polite about shutting down.

The second invocation shares nothing with the first except the `thread_id` and the SQLite file.
Watch what it prints: exactly one node update, from `escalate`. The triage node does not run again,
so the one call in this graph that costs money is paid for once, and the state it produced is read
off disk.

**`durability="sync"` is doing real work here, and it is not the default.** LangGraph defaults to
`durability="async"`, which writes the checkpoint while the next step is already running. That is
faster, and it is fine when a run ends by raising, but it means a hard kill can take the most
recent step with it: run this demo without `durability="sync"` and Saturday's process finds
nothing, or finds the run one step behind, differing between attempts. `"sync"` commits each
step before the next one starts. For a workflow whose whole selling point is surviving the box
dying, that trade is worth making explicit.

Run `python run_graph.py` for Day 1's non-durable version, which loses all of this on exit.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

import scoutbot.graph as graph_module
from scoutbot import build_ticket_graph, initial_state, sqlite_checkpointer, thread_config

load_dotenv()

DB_PATH = Path(__file__).parent / "checkpoints.db"

# One ticket, deliberately the Friday refund one from the coaches' page. Its ID doubles as the
# thread ID: one ticket is one run, so the ticket's own identifier is the natural key.
TICKET_ID = "T-4471"
TICKET_TEXT = (
    "I was charged twice for my annual plan and I want one of the charges refunded today."
)
CUSTOMER_ID = "1001"

WATCHED_FIELDS = ("triage", "approval", "resolution", "notes")


def _the_box_restarts(state):
    """Kills the process from inside the escalate node.

    Swapped in for `escalate_node` in the crash run only, and only in this process. A demo script
    is the right place for this: the graph in `src/scoutbot/graph.py` stays free of test hooks and
    crash flags, and the mechanism is visible in the file you are reading rather than hidden behind
    an environment variable.
    """
    print("\n  *** the box restarts. no cleanup, no goodbye. ***")
    print(f"  now run: python {Path(__file__).name}")
    sys.stdout.flush()
    os._exit(1)


def _graph():
    """Same builder as always, handed a file-backed saver. That argument is the entire change."""
    return build_ticket_graph(sqlite_checkpointer(DB_PATH))


def _reset_database() -> None:
    """Remove the database and its write-ahead log, so each demo starts from nothing.

    The `-wal` and `-shm` companions matter: SQLite runs in WAL mode here, so deleting only the
    main file would leave a previous run's committed data behind to be recovered.
    """
    for suffix in ("", "-wal", "-shm"):
        Path(str(DB_PATH) + suffix).unlink(missing_ok=True)


def _print_fields(indent: str, data: dict) -> None:
    for field in WATCHED_FIELDS:
        if data.get(field):
            print(f"{indent}{field}: {json.dumps(data[field])}")


def crash_phase() -> None:
    """Friday: start the run, and have the process die once it reaches the escalate node."""
    _reset_database()
    graph_module.escalate_node = _the_box_restarts

    print(f"FRIDAY 4:50pm  ticket {TICKET_ID}, checkpoints -> {DB_PATH.name}")
    graph = _graph()

    for chunk in graph.stream(
        initial_state(TICKET_TEXT, CUSTOMER_ID, TICKET_ID),
        thread_config(TICKET_ID),
        stream_mode="updates",
        durability="sync",
    ):
        for node_name, update in chunk.items():
            print(f"  ran {node_name!r}, which wrote:")
            _print_fields("      ", update)


def resume_phase() -> None:
    """Saturday: a fresh process picks the same run up from disk and finishes it."""
    if not DB_PATH.exists():
        print(f"No {DB_PATH.name} yet. Run: python {Path(__file__).name} --crash")
        return

    graph = _graph()
    config = thread_config(TICKET_ID)
    snapshot = graph.get_state(config)

    print(f"SATURDAY 9am   new process, nothing in memory, thread_id={TICKET_ID!r}")
    print("  what was on disk:")
    _print_fields("      ", snapshot.values)
    print(f"  what still has to run: {snapshot.next or '(nothing, this run finished)'}")

    if not snapshot.next:
        return

    print("\n  resuming with stream(None, config), which means 'use what is on the thread'...")
    for chunk in graph.stream(None, config, stream_mode="updates", durability="sync"):
        for node_name, update in chunk.items():
            print(f"  ran {node_name!r}, which wrote:")
            _print_fields("      ", update)

    print("\n  final state:")
    _print_fields("      ", graph.get_state(config).values)
    print("\n  note which node did NOT run just now: 'triage_ticket'. It completed on Friday, so")
    print("  its result came off disk and the model was not called a second time.")


def main() -> None:
    if "--crash" in sys.argv:
        crash_phase()
    else:
        resume_phase()


if __name__ == "__main__":
    main()
