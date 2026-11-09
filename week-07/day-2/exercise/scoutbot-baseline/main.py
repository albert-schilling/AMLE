"""Entry point: run ScoutBot's triage on the sample tickets and print the validated result.

Usage:
    python main.py
"""
import json
from pathlib import Path

from dotenv import load_dotenv

from scoutbot import triage

load_dotenv()

TICKETS_PATH = Path(__file__).parent / "sample_tickets.json"


def main():
    tickets = json.loads(TICKETS_PATH.read_text())
    for ticket in tickets:
        result = triage(ticket["text"])
        print(f"{ticket['id']}: {ticket['text'][:60]}...")
        print(f"  -> {result.model_dump()}")
        print()


if __name__ == "__main__":
    main()
