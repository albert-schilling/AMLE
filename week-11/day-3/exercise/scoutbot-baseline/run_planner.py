"""Week 11 Day 2 demo: a model-backed planner drives the supervisor team, metered end to end.

Unlike Day 1's `run_orchestrator.py`, this needs an **ANTHROPIC_API_KEY**: the planner is a real (cheap)
model call - that is the whole point of the day. Watch two things in the output:

- the **plan** the model wrote for each ticket, and the transcript showing the supervisor consulting each
  specialist in that order (a multi-part ticket really does visit several workers); and
- the **cost + latency** of every planning call, gathered on one `Meter`, with a per-ticket line and a
  grand total at the end. Note the planner picks its own tier: a one-line question plans on Haiku, a
  multi-part ticket on Sonnet (see `metering.pick_model` / `planner.assess_difficulty`).

The workers themselves make no model call (they reuse ScoutBot's rules table, an order lookup, and
retrieval), so the metered cost here is the planning call - which is exactly the call this day added.
"""
from scoutbot.metering import Meter
from scoutbot.orchestrator import initial_state
from scoutbot.planner import build_planning_team

TICKETS = [
    ("T-2001", "How long do refunds usually take to show up?", "1002", 0.0),
    ("T-2002", "Please check your refund policy, then refund my double charge of 40 euros.", "1001", 40.0),
    ("T-2003", "First tell me if I'm eligible for a refund, then refund me, and where is order ORD-1042?", "1001", 120.0),
]


def main() -> None:
    meter = Meter()
    team = build_planning_team(meter=meter)  # real planner (needs a key); real mock files + policy corpus
    for ticket_id, text, customer_id, refund_amount in TICKETS:
        state = initial_state(ticket_id, text, customer_id, refund_amount)
        out = team.invoke(state)
        print("=" * 96)
        print(f"{ticket_id}  ({customer_id}): {text}")
        print(f"  plan      : {out['plan'] if out.get('plan') else '(spent)'}  ")
        print(f"  transcript: {' -> '.join(out['transcript'])}")
        print(f"  answer    : {out['answer']}")
    print("=" * 96)
    print("Cost + latency for the planning calls this run:")
    print(meter.report())


if __name__ == "__main__":
    main()
