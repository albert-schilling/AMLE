"""The day's centrepiece: one run, watched as it happens, stopped on purpose, then finished.

Same Friday refund ticket. Two commands, and the gap between them can be any length at all:

    python run_events.py              # runs until ScoutBot needs a person, then exits
    python run_events.py --approve    # a person answers; the run finishes
    python run_events.py --reject     # or answers the other way

The first command shows both halves of the day at once. Watch the reply arrive a phrase at a time,
while the node that is writing it has not returned anything yet: those are `custom` events, pushed
out by `get_stream_writer()` from inside `draft_reply`. Then watch the run stop with a question on
screen. That is an `__interrupt__` event, on the same stream, and the process exits immediately
afterwards. Nothing is holding the ticket open.

The second command is the part worth dwelling on. It shares nothing with the first except a
`thread_id` and a SQLite file, and it prints exactly one node update, from `escalate`. Neither model
call runs again: the triage decision and the drafted reply both come off disk. What the human typed
arrives inside the node as the return value of the `interrupt()` call it stopped at.

Two details that are easy to get wrong, both verified rather than assumed:

- **No `durability="sync"` here, unlike `run_resume.py`, and that is deliberate.** Tuesday needed it
  because the process was *killed* mid-step. A pause is the opposite: the run ends cleanly, so the
  default durability commits it. Worth knowing so the argument does not become a superstition.
- **Resuming needs `Command(resume=value)`.** Passing the initial state again does not raise and
  does not resume. It restarts the graph from the top *on top of* the state already there, so the
  accumulating field ends up with every note twice, both model calls are paid for again, and the run
  arrives back at the same pause. `--wrong-resume` demonstrates it, since a bug you can watch is
  worth more than a warning you can read. Same shape as Tuesday's version of this mistake, which is
  worth pointing out: one rule covers both days.

**Carried forward into Day 4, and slightly different because of it.** The graph now applies an
approval policy before it pauses, so the payload names the approver it needs rather than asking an
anonymous human, and the resumed run continues past `escalate` into `send_reply`, which means an
email is actually sent at the end. That send is not this script's topic: see `run_approval.py`, which
exists to show the policy and the once-only guarantee properly. This ticket carries no refund amount,
so it escalates on triage priority alone and a support lead is enough to sign it.

Run `python run_graph.py` for the version of this run without a pause in it.
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from langgraph.types import Command

from scoutbot import build_ticket_graph, initial_state, sqlite_checkpointer, thread_config

load_dotenv()

DB_PATH = Path(__file__).parent / "checkpoints.db"

# The Friday refund ticket from the coaches' page. Its ID doubles as the thread ID: one ticket is
# one run, so the ticket's own identifier is the natural key.
TICKET_ID = "T-4471"
TICKET_TEXT = (
    "I was charged twice for my annual plan and I want one of the charges refunded today."
)
CUSTOMER_ID = "1001"

REVIEWER = "priya"


def _graph():
    """A file-backed checkpointer, so the pause outlives this process.

    `InMemorySaver` would be enough to *see* a pause work, and is what the tests use, but it lives
    in the process that is about to exit. A ticket waiting for a human has to wait somewhere real.
    """
    return build_ticket_graph(sqlite_checkpointer(DB_PATH))


def _reset_database() -> None:
    """Delete the SQLite file and its journal, so a demo always starts from nothing.

    The `-wal` and `-shm` files matter as much as the database itself: leave a stale journal behind
    and the next run picks up a half-finished thread, which looks like the demo misbehaving.
    """
    for path in (DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm")):
        path.unlink(missing_ok=True)


def start_phase() -> None:
    """Run until ScoutBot needs a person, showing every event as it arrives."""
    _reset_database()
    graph = _graph()
    config = thread_config(TICKET_ID)

    print(f"=== {TICKET_ID}: {TICKET_TEXT[:60]}... ===\n")
    drafting = False
    for mode, chunk in graph.stream(
        initial_state(TICKET_TEXT, CUSTOMER_ID, TICKET_ID),
        config,
        stream_mode=["updates", "custom"],
    ):
        if mode == "custom":
            # Arrives while `draft_reply` is still running. The node has returned nothing yet.
            if not drafting:
                print("  draft, as it is written:\n")
                print("      ", end="", flush=True)
                drafting = True
            print(chunk["draft_chunk"], end="", flush=True)
            continue

        for node_name, update in chunk.items():
            if drafting:
                print("\n")
                drafting = False
            if node_name == "__interrupt__":
                payload = update[0].value
                print("  the run STOPPED and is waiting for a person:\n")
                print(f"      question: {payload['question']}")
                print(f"      why:      {payload['why']}")
                print(f"      account:  {payload['account']}")
                continue
            print(f"  node {node_name!r} finished: {json.dumps(update.get('notes', []))}")

    snapshot = graph.get_state(config)
    print(f"\n  next node still owed: {snapshot.next}")
    print("  this process is about to exit. The ticket is not lost, and nothing is blocked.")
    print("  answer it with: python run_events.py --approve")


def resume_phase(approved: bool) -> None:
    """Answer the question, in a completely separate process, and let the run finish."""
    graph = _graph()
    config = thread_config(TICKET_ID)

    snapshot = graph.get_state(config)
    if not snapshot.next:
        print("Nothing is waiting on this thread. Run `python run_events.py` first.")
        return

    print(f"=== {TICKET_ID}, resumed in a new process ===\n")
    print(f"  waiting at:      {snapshot.next}")
    print(f"  drafted earlier: {snapshot.values['draft_reply'][:60]}...")
    print(f"  triaged earlier: {json.dumps(snapshot.values['triage'])}\n")
    print(f"  {REVIEWER} says: {'approve' if approved else 'reject'}\n")

    # `Command(resume=...)` and nothing else. The dict below is what the `interrupt()` call inside
    # `escalate_node` returns; LangGraph does not inspect or validate it on the way through.
    for mode, chunk in graph.stream(
        Command(resume={"approved": approved, "by": REVIEWER, "role": "support_lead"}),
        config,
        stream_mode=["updates", "custom"],
    ):
        if mode == "custom":
            print(f"  unexpected custom event: {chunk}")
            continue
        for node_name, update in chunk.items():
            print(f"  node {node_name!r} finished: {json.dumps(update.get('notes', []))}")

    final = graph.get_state(config)
    print(f"\n  resolution: {json.dumps(final.values['resolution'])}")
    print(f"  notes:      {json.dumps(final.values['notes'])}")
    print("  no model call in this process: both the triage and the draft came off disk.")


def wrong_resume_phase() -> None:
    """The teachable bug: resume with the initial state instead of `Command(resume=...)`."""
    graph = _graph()
    config = thread_config(TICKET_ID)

    before = graph.get_state(config)
    if not before.next:
        print("Nothing is waiting on this thread. Run `python run_events.py` first.")
        return

    print(f"  waiting at:     {before.next}")
    print(f"  notes so far:   {len(before.values['notes'])}")
    print("  resuming with the initial state instead of Command(resume=...):\n")
    graph.invoke(initial_state(TICKET_TEXT, CUSTOMER_ID, TICKET_ID), config)

    after = graph.get_state(config)
    print(f"      resolution:    {json.dumps(after.values['resolution'])}")
    print(f"      still waiting: {after.next}")
    print(f"      notes now:     {len(after.values['notes'])}")
    for note in after.values["notes"]:
        print(f"          {note}")
    print("\n  No exception, and no progress. Passing input restarts the graph from the top on")
    print("  top of the state that was already there, so every note is duplicated and both")
    print("  model calls were paid for again. Then it reached the same pause and stopped again.")


def main() -> None:
    flags = set(sys.argv[1:])
    if "--approve" in flags:
        resume_phase(approved=True)
    elif "--reject" in flags:
        resume_phase(approved=False)
    elif "--wrong-resume" in flags:
        wrong_resume_phase()
    else:
        start_phase()


if __name__ == "__main__":
    main()
