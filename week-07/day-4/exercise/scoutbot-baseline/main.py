"""Entry point: run ScoutBot's Day 2 agent loop on the sample tickets and print the full
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


def main():
    # No approve_fn passed - falls back to tools.py's interactive y/n prompt, so an
    # escalate_to_human call actually pauses here and waits for you.
    tickets = json.loads(TICKETS_PATH.read_text())
    for ticket in tickets:
        print(f"=== {ticket['id']}: {ticket['text'][:60]}... ===")
        result = run_agent_loop(ticket["text"], ticket["customer_id"])
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
