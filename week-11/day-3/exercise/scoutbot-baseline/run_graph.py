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
call passes a `thread_config`, because a paused run needs a name, and a ticket that needs a human
stops early with an `__interrupt__` update instead of reaching a resolution. That is not this
script's topic, so it prints one line and points at `run_approval.py`.

Day 4 adds `approval` to the watched fields, which makes this script a decent way to see the policy
applied across every sample ticket at once: two of them auto-approve and send, and the rest stop for
a named approver. Note that the tickets now carry a `refund_amount`, and it is passed in rather than
derived, because it is a billing fact rather than something any node here works out.

Usage:
    python run_graph.py
"""
import json
from pathlib import Path

from dotenv import load_dotenv

from scoutbot import build_ticket_graph, initial_state, thread_config

load_dotenv()

TICKETS_PATH = Path(__file__).parent / "sample_tickets.json"
WATCHED_FIELDS = ("customer", "triage", "draft_reply", "approval", "resolution", "notes")


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
        print(f"=== {ticket['id']}: EUR {ticket['refund_amount']:.2f} | "
              f"{ticket['text'][:45]}... ===")
        state = initial_state(
            ticket["text"],
            ticket["customer_id"],
            ticket["id"],
            refund_amount=ticket["refund_amount"],
        )

        first_snapshot = True
        # The config is new as of Day 3. A ticket that needs a human now stops inside `escalate`,
        # and a paused run has to be filed under a `thread_id` to be resumable, so every call needs
        # one. `run_approval.py` is where the pause and the send are actually explored; here it just
        # shows up as an `__interrupt__` update and the run ending early.
        for mode, chunk in graph.stream(
            state, thread_config(ticket["id"]), stream_mode=["updates", "values"]
        ):
            if mode == "updates":
                for node_name, update in chunk.items():
                    if node_name == "__interrupt__":
                        required = update[0].value.get("approver_required", "a human")
                        print(f"  the run stopped, waiting for: {required}. "
                              "See run_approval.py.")
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
