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

ISSUE_REFUND_TOOL = {
    "name": "issue_refund",
    "description": (
        "Issue a refund to a customer's account. This MOVES MONEY and cannot be undone. Provide the "
        "customer_id and the amount in euros. Refunds above the policy limit, or on accounts that "
        "have already been refunded several times recently, require human approval before they take "
        "effect - so calling it is safe even when you are unsure, because the guard will stop it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "The customer's account ID."},
            "amount": {"type": "number", "description": "Refund amount in euros."},
        },
        "required": ["customer_id", "amount"],
    },
}


def look_up_customer(customer_id: str) -> dict:
    customers = json.loads(CUSTOMERS_PATH.read_text())
    record = customers.get(customer_id)
    if record is None:
        return {"found": False, "customer_id": customer_id}
    return {"found": True, **record}


def refund_key(customer_id: str, amount: float) -> str:
    """The idempotency key for "this refund has been issued", keyed on the account and the amount.

    Same discipline as `notify.reply_key` from Week 8 Day 4: one definition of what counts as the
    same action, derived from the request rather than generated per attempt, so a retried or repeated
    call produces the *same* key and the ledger can recognise it. Keying on `(customer_id, amount)`
    means "refund EUR 900 to account 1001" is one action however many times it is asked for; a
    genuinely different refund (a different amount) is a different key, as it should be.
    """
    return f"{customer_id}:refund:{amount:.2f}"


def issue_refund(customer_id: str, amount: float, ledger=None) -> dict:
    """Issue a refund, at most once per (customer, amount), however often this is called.

    This is the one tool in the loop with an irreversible side effect - it moves money - so it
    carries the same idempotency guard as Week 8 Day 4's `send_reply`: check the ledger first, do the
    irreversible thing, then record it immediately. A repeated call finds the key already recorded and
    returns a skip instead of paying twice.

    Note the split of responsibilities. This function guarantees the refund happens *at most once*;
    it does **not** decide whether the refund is *allowed* - that is the job of the `refund_guard`
    pre-hook (see `hooks.py`), which runs before this and can block the call entirely. Authorisation
    is a guard; once-only is the tool's own contract. Passing `ledger=None` skips the dedup (handy in
    a quick demo), but any real call should pass a durable ledger.
    """
    key = refund_key(customer_id, amount)
    if ledger is not None and ledger.already_done(key):
        return {"issued": False, "skipped": True, "key": key, "reason": "already refunded"}
    # The irreversible bit (mocked here - a real system would call the payments API).
    if ledger is not None:
        ledger.record(key, detail=f"refunded EUR {amount:.2f} to {customer_id}")
    return {
        "issued": True,
        "skipped": False,
        "key": key,
        "customer_id": customer_id,
        "amount": amount,
    }


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
