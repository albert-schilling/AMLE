"""Week 10 Day 4 in one script: the same triage contract, produced two ways.

`core.triage` (Week 7) and `typed_agent.triage` (today) return the *same* `TicketTriage`. The difference
is everything around it: the raw-SDK path hand-writes the tool schema, forces the tool call, digs the
`tool_use` block out of the response, validates it, and retries in a `try/except`; the Pydantic AI path
asks for `output_type=TicketTriage` and lets the framework derive the schema, validate the reply, run the
output validators, and retry. This script runs the framework path on a few sample tickets and prints the
validated result.

Needs a real key (`ANTHROPIC_API_KEY`) because it makes real model calls - the *offline* proof is in the
tests (`tests/test_typed_agent.py`), which pass `TestModel`/`FunctionModel` and never reach the network.

    python run_typed.py
"""
from scoutbot.typed_agent import triage

TICKETS = [
    "I was charged twice for my subscription this month. Please refund the extra charge.",
    "The app crashes every time I tap the export button on the reports screen.",
    "Hi! Just wanted to say thanks, the new dashboard is lovely. That's all.",
    "I can't log in and I think someone else changed my account email overnight.",
]


def main():
    print("Framework-native triage (Pydantic AI, output_type=TicketTriage):\n")
    for ticket in TICKETS:
        result = triage(ticket)  # returns a validated TicketTriage, retried once on a schema/rule miss
        print(f"  ticket:   {ticket[:64]}")
        print(f"  category: {result.category.value}")
        print(f"  priority: {result.priority.value}")
        print(f"  owner:    {result.suggested_owner}\n")

    print("Same TicketTriage contract as Week 7's core.triage - the framework did the plumbing, not us.")


if __name__ == "__main__":
    main()
