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

Two small changes on Day 3, both consequences of `escalate` now pausing rather than ending: every
call passes a `thread_config`, because a paused run needs a name, and a high-priority ticket stops
early with an `__interrupt__` update instead of reaching a resolution. That is not this script's
topic, so it prints one line and points at `run_events.py`.

Usage:
    python run_graph.py
"""
import json
from pathlib import Path

from dotenv import load_dotenv

from scoutbot import build_ticket_graph, initial_state, thread_config

load_dotenv()

TICKETS_PATH = Path(__file__).parent / "sample_tickets.json"
WATCHED_FIELDS = ("customer", "triage", "draft_reply", "resolution", "notes")


def _print_fields(indent: str, data: dict, fields=WATCHED_FIELDS) -> None:
    for field in fields:
        if field not in data:
            continue
        rendered = json.dumps(data[field])
        # `draft_reply` is a few sentences of prose, which would bury everything else.
        if len(rendered) > 70:
            rendered = f"{rendered[:70]}..."
        print(f"{indent}{field}: {rendered}")


def main():
    # Compiled once and reused for every ticket - a compiled graph is a reusable object, not a
    # per-run one.
    graph = build_ticket_graph()
    tickets = json.loads(TICKETS_PATH.read_text())

    for ticket in tickets:
        print(f"=== {ticket['id']}: {ticket['text'][:60]}... ===")
        state = initial_state(ticket["text"], ticket["customer_id"], ticket["id"])

        first_snapshot = True
        # The config is new as of Day 3. A high-priority ticket now stops inside `escalate` to
        # ask a human, and a paused run has to be filed under a `thread_id` to be resumable, so
        # every call needs one. `run_events.py` is where that pause is actually explored; here it
        # just shows up as an `__interrupt__` update and the run ending early.
        for mode, chunk in graph.stream(
            state, thread_config(ticket["id"]), stream_mode=["updates", "values"]
        ):
            if mode == "updates":
                for node_name, update in chunk.items():
                    if node_name == "__interrupt__":
                        print("  the run stopped to ask a human. See run_events.py.")
                        continue
                    print(f"  node {node_name!r} returned only:")
                    _print_fields("      ", update)
            else:
                print(f"  {'starting state:' if first_snapshot else 'state is now:'}")
                _print_fields("      ", chunk)
                first_snapshot = False
        print()


if __name__ == "__main__":
    main()
