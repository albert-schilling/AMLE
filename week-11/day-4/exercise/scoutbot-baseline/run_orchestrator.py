"""Week 11 Day 1 demo: one ticket, routed to one specialist, by an orchestrator.

Run it and watch the transcript: `look_up_customer` runs once, `dispatch` picks a specialty, exactly one
worker subgraph runs, and every route rejoins at `finalize`. Three tickets, three specialists, one team.

Notably, this demo needs **no ANTHROPIC_API_KEY**: the dispatcher is a deterministic keyword rule and the
workers reuse ScoutBot's rules table, an order lookup, and retrieval - so the whole thing runs offline. (The
research worker builds the embedding index on first use, which downloads the model once; refund and order
touch neither a model nor the network.)
"""
from scoutbot.orchestrator import build_orchestrator, initial_state

TICKETS = [
    ("T-1001", "I was charged twice for my subscription and need a refund - this is the third time!", "1001", 900.0),
    ("T-1002", "Where is my order ORD-1042? It still hasn't arrived.", "1001", 0.0),
    ("T-1003", "How do I export my monthly report to CSV from the dashboard?", "1002", 0.0),
]


def main() -> None:
    team = build_orchestrator()  # real collaborators: mock customer/order files + the policy corpus
    for ticket_id, text, customer_id, refund_amount in TICKETS:
        state = initial_state(ticket_id, text, customer_id, refund_amount)
        out = team.invoke(state)
        print("=" * 88)
        print(f"{ticket_id}  ({customer_id}): {text}")
        print(f"  route     : dispatch -> {out['specialty']}")
        print(f"  transcript: {' -> '.join(out['transcript'])}")
        print(f"  answer    : {out['answer']}")
    print("=" * 88)


if __name__ == "__main__":
    main()
