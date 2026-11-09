"""The day's centrepiece: a policy decides who signs, and the reply goes out exactly once.

Same Friday refund ticket, now with a number on it. Four commands:

    python run_approval.py                    # policy decides, run stops for the named approver
    python run_approval.py --approve           # the right person signs; the reply is sent
    python run_approval.py --approve-wrong-role # the wrong person signs; nothing is sent
    python run_approval.py --flaky             # the mail gateway misbehaves; still one email

The first command prints the policy's decision and the rule behind it, then stops with a payload that
says *which* approver is required rather than asking an anonymous "human". Nine hundred euros needs a
billing manager, and it says so.

The second finishes the run in a separate process, and this is where today differs from yesterday:
the run does not merely record an approval, it reaches `send_reply` and an email actually leaves.

The third is the interesting failure. Priya is a support lead, and she is not allowed to sign a
billing manager's decision. `escalate_node` checks, records a non-approval with a reason, and
`send_reply` sends nothing. Worth doing in front of the room, because the payload's `approver_required`
field is advisory and nothing stops a caller ignoring it: the *check* is what makes it a rule.

Note that the refused run *finishes*, refused, rather than pausing again to wait for somebody better.
So the demo order is: `run_approval.py`, `--approve-wrong-role` (nothing sent), then `run_approval.py`
again to start a fresh thread, then `--approve`. Re-pausing until an authorised approver turns up is a
deliberate non-feature here: it needs a second `interrupt()` on a loop, which is the early-finish
extension in `exercises.md` rather than today's lecture.

The fourth is the one to spend time on. `--flaky` makes the mail gateway accept the message and then
drop the connection, twice, so LangGraph's `RetryPolicy` runs `send_reply` three times over. Without
the ledger the customer would get three identical emails. Watch the attempt counter climb, the ledger
suppress attempts two and three, and the final row printed from SQLite.

Two details worth knowing before demonstrating any of this, both verified locally:

- **Where the failure sits decides whether the ledger matters at all.** `--flaky` fails *after* the
  send, which is the realistic case: the gateway took the mail, then the connection died, so our code
  never learned it had succeeded. Put the same failure *above* the send and a retry never reaches the
  send, one email goes out regardless, and the ledger looks like ceremony.
- **No `durability="sync"` here, unlike `run_resume.py`.** A pause ends the run cleanly, so the
  default commits it. The ledger is a separate table in the same SQLite file, so a run's progress and
  its effects on the world live in one place.

Run `python run_events.py` for yesterday's version, which pauses but never sends anything.
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from langgraph.types import Command

from scoutbot import (
    Ledger,
    build_ticket_graph,
    initial_state,
    reset_flaky_counter,
    sqlite_checkpointer,
    thread_config,
)

load_dotenv()

DB_PATH = Path(__file__).parent / "checkpoints.db"

# The Friday refund ticket, now with the disputed charge attached to it. The amount is a billing
# fact looked up alongside the ticket, never something read out of what the customer wrote.
TICKET_ID = "T-4471"
TICKET_TEXT = (
    "I was charged twice for my annual plan and I want one of the charges refunded today."
)
CUSTOMER_ID = "1001"
REFUND_AMOUNT = 900.0

# Two people, and what they are. The role is the part the policy checks; the name is the part an
# audit trail needs. In a real system both would come from a signed session rather than from a
# constant, which is the honest caveat to state when demonstrating this.
DANA = {"by": "dana", "role": "billing_manager"}
PRIYA = {"by": "priya", "role": "support_lead"}


def _graph(fail_after_send: int = 0):
    """A file-backed checkpointer and a file-backed ledger, in the same database.

    Both default to in-memory when not passed, and both defaults would work right up until this
    process exits. A ticket waiting for a human, and a record of what was already sent to that
    customer, both have to survive longer than that.
    """
    return build_ticket_graph(
        checkpointer=sqlite_checkpointer(DB_PATH),
        ledger=Ledger.at(DB_PATH),
        fail_after_send=fail_after_send,
    )


def _reset_database() -> None:
    """Delete the SQLite file and its journal, so a demo always starts from nothing.

    The `-wal` and `-shm` files matter as much as the database itself: leave a stale journal behind
    and the next run picks up a half-finished thread, which looks like the demo misbehaving. Note
    that this also wipes the ledger, which is the correct behaviour for a demo and would be an
    outage in production.
    """
    for path in (DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm")):
        path.unlink(missing_ok=True)
    reset_flaky_counter()


def _print_notes(node_name: str, update: dict) -> None:
    for note in update.get("notes", []):
        print(f"  {node_name}: {note}")


def start_phase() -> None:
    """Run until the policy's chosen approver is needed, then stop."""
    _reset_database()
    graph = _graph()
    config = thread_config(TICKET_ID)

    print(f"=== {TICKET_ID}: EUR {REFUND_AMOUNT:.2f} refund request ===\n")
    for mode, chunk in graph.stream(
        initial_state(TICKET_TEXT, CUSTOMER_ID, TICKET_ID, refund_amount=REFUND_AMOUNT),
        config,
        stream_mode=["updates", "custom"],
    ):
        if mode == "custom":
            continue  # the draft streams here; yesterday's demo is the one that shows it
        for node_name, update in chunk.items():
            if node_name == "__interrupt__":
                payload = update[0].value
                print("\n  the run STOPPED, and it knows who it is waiting for:\n")
                print(f"      question:  {payload['question']}")
                print(f"      requires:  {payload['approver_required']}")
                print(f"      because:   {payload['why']}")
                print(f"      amount:    EUR {payload['amount']:.2f}")
                print(f"      account:   {payload['account']}")
                continue
            _print_notes(node_name, update)

    snapshot = graph.get_state(config)
    print(f"\n  next node still owed: {snapshot.next}")
    print("  nothing has been sent to the customer yet.")
    print("  a billing manager can finish it:  python run_approval.py --approve")
    print("  or watch a support lead try:       python run_approval.py --approve-wrong-role")
    print("  (a refused run ends refused, so re-run this command before --approve)")


def resume_phase(reviewer: dict, fail_after_send: int = 0) -> None:
    """Answer the question in a separate process, and let the reply actually go out."""
    graph = _graph(fail_after_send=fail_after_send)
    config = thread_config(TICKET_ID)

    snapshot = graph.get_state(config)
    if not snapshot.next:
        print("Nothing is waiting on this thread. Run `python run_approval.py` first.")
        return

    required = snapshot.values["approval"]["approver"]
    print(f"=== {TICKET_ID}, resumed in a new process ===\n")
    print(f"  waiting at:  {snapshot.next}")
    print(f"  policy says: {required} must approve ({snapshot.values['approval']['reason']})")
    print(f"  answering as: {reviewer['by']}, a {reviewer['role']}\n")
    if fail_after_send:
        print(f"  the mail gateway will drop the connection {fail_after_send}x AFTER accepting\n")

    # `Command(resume=...)` and nothing else. The dict below is what the `interrupt()` call inside
    # `escalate_node` returns; LangGraph does not inspect or validate it on the way through, which
    # is exactly why the node checks the role itself.
    for mode, chunk in graph.stream(
        Command(resume={"approved": True, **reviewer}),
        config,
        stream_mode=["updates", "custom"],
    ):
        if mode == "custom":
            continue
        for node_name, update in chunk.items():
            _print_notes(node_name, update)

    final = graph.get_state(config)
    print(f"\n  resolution: {json.dumps(final.values['resolution'])}")
    _print_ledger()


def _print_ledger() -> None:
    """What the ledger has to say about this ticket, straight out of SQLite."""
    rows = Ledger.at(DB_PATH).entries()
    print("\n  side_effects table:")
    if not rows:
        print("      (empty: nothing was sent)")
    for key, detail, created_at in rows:
        print(f"      {key}  |  {detail}  |  {created_at}")
    print(f"      {len(rows)} row(s), so the customer received {len(rows)} email(s).")


def flaky_phase() -> None:
    """The whole day in one command: policy, pause, approval, and a retry that sends once."""
    _reset_database()
    print("--- phase 1: run until the approver is needed ---\n")
    graph = _graph()
    config = thread_config(TICKET_ID)
    graph.invoke(
        initial_state(TICKET_TEXT, CUSTOMER_ID, TICKET_ID, refund_amount=REFUND_AMOUNT),
        config,
    )
    snapshot = graph.get_state(config)
    print(f"  stopped at {snapshot.next}, needing {snapshot.values['approval']['approver']}")

    print("\n--- phase 2: the right person approves, and the gateway misbehaves ---\n")
    resume_phase(DANA, fail_after_send=2)
    print("\n  three attempts at send_reply, one email. The two retries found the ledger row")
    print("  their own first attempt had written, and did not send again.")


def main() -> None:
    flags = set(sys.argv[1:])
    if "--approve" in flags:
        resume_phase(DANA)
    elif "--approve-wrong-role" in flags:
        resume_phase(PRIYA)
    elif "--flaky" in flags:
        flaky_phase()
    else:
        start_phase()


if __name__ == "__main__":
    main()
