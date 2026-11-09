"""Entry point: run ScoutBot's agent loop on the sample tickets and print the full
Thought/Action/Observation trace for each, plus the final answer.

Usage:
    python main.py
"""
import json
from pathlib import Path

from dotenv import load_dotenv

from scoutbot import run_agent_loop

load_dotenv()

TICKETS_PATH = Path(__file__).parent / "sample_tickets.json"
LOG_PATH = Path(__file__).parent / "sample_app.log"

# T-2002 asks ScoutBot to compute something over the app log, so it needs the log's actual
# content in front of it - not just a filename it has no way to open on its own. We inline
# the raw text into the ticket message here, in main.py, rather than inside loop.py: the loop
# itself shouldn't need to know which tickets happen to come with an attachment.
TICKETS_WITH_LOG_ATTACHED = {"T-2002"}


def _ticket_text(ticket: dict) -> str:
    if ticket["id"] in TICKETS_WITH_LOG_ATTACHED:
        return f"{ticket['text']}\n\nHere is today's app log:\n{LOG_PATH.read_text()}"
    return ticket["text"]


def main():
    # No approve_fn passed - falls back to tools.py's interactive y/n prompt, so an
    # escalate_to_human call actually pauses here and waits for you.
    tickets = json.loads(TICKETS_PATH.read_text())
    for ticket in tickets:
        print(f"=== {ticket['id']}: {ticket['text'][:60]}... ===")
        result = run_agent_loop(_ticket_text(ticket), ticket["customer_id"])
        for i, step in enumerate(result.steps, start=1):
            print(f"  Step {i} - Thought: {step.thought}")
            if step.action:
                print(f"           Action: {step.action}({step.action_input})")
                print(f"           Observation: {step.observation}")
        print(f"  Final answer: {result.final_answer}")
        print(f"  Escalated (hit step cap): {result.escalated}")
        print()


if __name__ == "__main__":
    main()
