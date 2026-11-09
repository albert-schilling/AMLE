"""ScoutBot's two new tools for the agent loop: a read-only lookup and a gated escalation.

Kept deliberately simple - a JSON file standing in for a real customer database, and a plain
confirm-prompt standing in for a real approval workflow (see Day 2 slides: Human-in-the-Loop
Gates). Both have plain dict schemas (no Pydantic model) since - unlike yesterday's
`TicketTriage` - nothing here needs to validate a *final* structured answer; these tools just
feed intermediate observations back into the loop.
"""
import json
from pathlib import Path
from typing import Callable, Optional

CUSTOMERS_PATH = Path(__file__).parent.parent.parent / "mock_customers.json"

LOOK_UP_CUSTOMER_TOOL = {
    "name": "look_up_customer",
    "description": (
        "Look up an existing customer's account info by customer_id. Read-only - has no "
        "side effects. Returns plan, account age, and recent refund history."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "The customer's account ID."},
        },
        "required": ["customer_id"],
    },
}

ESCALATE_TOOL = {
    "name": "escalate_to_human",
    "description": (
        "Hand this ticket off to a human agent. Use this when the ticket needs a real person "
        "- e.g. a refund decision, or anything you're not confident resolving yourself. "
        "Requires human approval before it takes effect."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "Why this ticket needs a human."},
        },
        "required": ["reason"],
    },
}


def look_up_customer(customer_id: str) -> dict:
    customers = json.loads(CUSTOMERS_PATH.read_text())
    record = customers.get(customer_id)
    if record is None:
        return {"found": False, "customer_id": customer_id}
    return {"found": True, **record}


def _default_approve(reason: str) -> bool:
    answer = input(f"[HUMAN APPROVAL NEEDED] Escalate ticket? Reason: {reason!r} (y/n): ")
    return answer.strip().lower().startswith("y")


def escalate_to_human(reason: str, approve_fn: Optional[Callable[[str], bool]] = None) -> dict:
    """Never fires without approval - `approve_fn` defaults to an interactive y/n prompt, but
    tests (and any non-interactive caller) can pass their own."""
    approve = approve_fn or _default_approve
    if not approve(reason):
        return {"approved": False, "note": "Escalation rejected by human reviewer."}
    return {"approved": True, "note": "Escalated to the human support queue."}
