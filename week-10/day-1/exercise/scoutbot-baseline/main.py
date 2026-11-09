"""Entry point: run ScoutBot's agent loop on the full sample ticket batch, printing the
full Thought/Action/Observation trace for each - then, once the whole batch has run,
answer a real question straight from the saved log file, without re-running anything.

Usage:
    python main.py
"""
import json
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from scoutbot import read_log, run_agent_loop

load_dotenv()

TICKETS_PATH = Path(__file__).parent / "sample_tickets.json"
APP_LOG_PATH = Path(__file__).parent / "sample_app.log"
TELEMETRY_LOG_PATH = Path(__file__).parent / "scoutbot_log.jsonl"

# T-2002 asks ScoutBot to compute something over the app log, so it needs the log's actual
# content in front of it - not just a filename it has no way to open on its own. We inline
# the raw text into the ticket message here, in main.py, rather than inside loop.py: the loop
# itself shouldn't need to know which tickets happen to come with an attachment.
TICKETS_WITH_LOG_ATTACHED = {"T-2002"}


def _ticket_text(ticket: dict) -> str:
    if ticket["id"] in TICKETS_WITH_LOG_ATTACHED:
        return f"{ticket['text']}\n\nHere is today's app log:\n{APP_LOG_PATH.read_text()}"
    return ticket["text"]


def _summarize_log(log_path: Path) -> None:
    """Answer three real questions straight from the saved JSONL file - no ticket gets
    re-run to produce any of these, they all come from records already on disk."""
    records = read_log(log_path)
    if not records:
        print("(no log records found)")
        return

    errored = [r for r in records if r["errored"]]
    slowest = max(records, key=lambda r: r["duration_ms"])
    tool_counts = Counter(r["tool"] or "(final answer, no tool)" for r in records)

    print(f"  Total steps logged: {len(records)}")
    print(f"  Steps that errored: {len(errored)}")
    print(
        f"  Slowest step: {slowest['ticket_id']} step {slowest['step']} "
        f"({slowest['tool']}, {slowest['duration_ms']} ms)"
    )
    print("  Tool usage:")
    for tool, count in tool_counts.most_common():
        print(f"    {tool}: {count}")


def main():
    # Fresh log each run, so re-running the batch doesn't silently double-count against
    # records left over from a previous run.
    TELEMETRY_LOG_PATH.unlink(missing_ok=True)

    # No approve_fn passed - falls back to tools.py's interactive y/n prompt, so an
    # escalate_to_human call actually pauses here and waits for you.
    tickets = json.loads(TICKETS_PATH.read_text())
    for ticket in tickets:
        print(f"=== {ticket['id']}: {ticket['text'][:60]}... ===")
        result = run_agent_loop(
            _ticket_text(ticket),
            ticket["customer_id"],
            ticket_id=ticket["id"],
            log_path=TELEMETRY_LOG_PATH,
        )
        for i, step in enumerate(result.steps, start=1):
            print(f"  Step {i} - Thought: {step.thought}")
            if step.action:
                print(f"           Action: {step.action}({step.action_input})")
                print(f"           Observation: {step.observation}")
        print(f"  Final answer: {result.final_answer}")
        print(f"  Escalated (hit step cap): {result.escalated}")
        print()

    print(f"=== Log saved to {TELEMETRY_LOG_PATH.name} - answering from it, not re-running ===")
    _summarize_log(TELEMETRY_LOG_PATH)


if __name__ == "__main__":
    main()
