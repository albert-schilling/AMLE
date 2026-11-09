"""Who has to approve this, and does anyone have to approve it at all.

This module is the whole of today's first topic, and the most important thing about it is what it
does *not* contain: no model call, no graph, no database, no LangGraph import, nothing that touches
the network. It is a table of rules over plain numbers and strings.

That is not tidiness for its own sake. Three things follow from it, and each one matters more than
the code does:

- **Dana can read it.** The person who owns a refund policy is not the person who wrote the agent.
  A rule expressed as `amount >= 500` in a function with a name is reviewable by someone who does
  not know what a `StateGraph` is. The same rule expressed as a sentence inside a prompt is not
  reviewable at all, it is a suggestion.
- **It is testable with a dict.** Every branch of the table can be checked in a test with no API
  key, no graph and no network, which is why `tests/test_policy.py` is the fastest file in the repo
  and covers the most decisions.
- **It cannot drift.** Tuesday's lesson was that policy in code does the same thing on every run,
  where a model asked to make the same judgement may not. Money is the case where that stops being
  an academic preference.

The split to keep in your head: **the model supplies judgement, this file supplies policy.** Triage
reads the ticket and decides what kind of problem it is and how urgent it feels, which is a genuine
judgement call and a good use of a model. What that judgement is *worth* in euros, and who is
allowed to sign it off, is not a judgement call. It is a rule someone wrote down, and it belongs
here.

Note where the amount comes from, too. It is looked up alongside the customer record, as a billing
fact, and never extracted from what the customer wrote. A customer claiming they were charged nine
hundred euros is a claim; the charge is a fact. Asking a model to read the number off the ticket
text would put the model in charge of the money by the back door, which is exactly what this file
exists to prevent.
"""
from dataclasses import dataclass
from typing import Optional

# The approval table, as three thresholds. Every number here is a business decision rather than a
# technical one, which is the argument for keeping them together, named, and at the top of a file
# somebody outside the team can be pointed at.
AUTO_APPROVE_UNDER = 50.0
"""Below this, in euros, ScoutBot sends its own reply and nobody is interrupted."""

LEAD_APPROVES_UNDER = 500.0
"""Below this a support lead can sign off. At or above it, a billing manager has to."""

REPEAT_REFUND_THRESHOLD = 3
"""This many refunds inside 90 days makes an account a repeat case, whatever the amount is."""

SUPPORT_LEAD = "support_lead"
BILLING_MANAGER = "billing_manager"
NOBODY = "scoutbot"

# Which roles are allowed to sign for which required approver. A billing manager can approve
# anything a support lead can, but not the other way around, and this is the only place that
# hierarchy is written down.
_AUTHORISED = {
    SUPPORT_LEAD: {SUPPORT_LEAD, BILLING_MANAGER},
    BILLING_MANAGER: {BILLING_MANAGER},
}


@dataclass(frozen=True)
class Approval:
    """What the policy decided, and why it decided it.

    `reason` exists because a decision a human cannot understand is a decision they cannot
    challenge. It goes straight into the pause payload, so the person being interrupted is told
    which rule pulled them in rather than being asked to guess.
    """

    needs_human: bool
    approver: str
    reason: str

    @property
    def route(self) -> str:
        """The node name this decision leads to, so the router stays a one-liner."""
        return "escalate" if self.needs_human else "auto_approve"


def decide_approval(
    amount: float,
    plan: str,
    past_refunds_90d: int,
    priority: str,
) -> Approval:
    """Decide whether a human is needed for this refund, and which human.

    Read top to bottom; the first rule that matches wins, and the order is the policy:

    1. A repeat refunder goes to a billing manager whatever the amount is. Three refunds in ninety
       days is a pattern, and a pattern is worth a person even when the euros are small.
    2. Anything at or above `LEAD_APPROVES_UNDER` goes to a billing manager.
    3. Anything at or above `AUTO_APPROVE_UNDER` goes to a support lead.
    4. A high-priority ticket still gets a human even when the amount is trivial, because
       "priority" is the model's judgement that something is wrong beyond the money.
    5. Everything else ScoutBot answers itself.

    Deliberately a function of four plain values rather than of the state dict. It keeps the module
    importable and testable without the rest of the package, and it makes the inputs to the decision
    impossible to miss: if a fifth fact starts mattering, the signature says so and every caller has
    to be updated. `approval_for_state()` below does the unpacking, in one place.

    `plan` is accepted and deliberately unused. It is the field a coach will be asked about ("should
    enterprise customers get a higher limit?"), and the honest answer is that it is a policy question
    for Dana, not a code question, so the parameter is here and the table does not read it yet.
    """
    if past_refunds_90d >= REPEAT_REFUND_THRESHOLD:
        return Approval(
            needs_human=True,
            approver=BILLING_MANAGER,
            reason=f"{past_refunds_90d} refunds in the last 90 days",
        )
    if amount >= LEAD_APPROVES_UNDER:
        return Approval(
            needs_human=True,
            approver=BILLING_MANAGER,
            reason=f"EUR {amount:.2f} is at or above the EUR {LEAD_APPROVES_UNDER:.0f} limit",
        )
    if amount >= AUTO_APPROVE_UNDER:
        return Approval(
            needs_human=True,
            approver=SUPPORT_LEAD,
            reason=f"EUR {amount:.2f} needs a second pair of eyes",
        )
    if priority == "high":
        return Approval(
            needs_human=True,
            approver=SUPPORT_LEAD,
            reason="triaged high priority, so a person should see it",
        )
    return Approval(
        needs_human=False,
        approver=NOBODY,
        reason=f"EUR {amount:.2f} on a clean account, under every threshold",
    )


def approval_for_state(state: dict) -> Approval:
    """Apply the table to a run's state. The only place the two vocabularies meet.

    Defaults are chosen so a half-built state cannot accidentally auto-approve: a missing amount
    reads as 0.0, but a missing refund count reads as 0 and a missing priority as `""`, so the
    worst a malformed state gets is the no-human branch on a zero-euro ticket. If that ever needs to
    fail loudly instead, this function is the one place to change.
    """
    customer = state.get("customer") or {}
    triage = state.get("triage") or {}
    return decide_approval(
        amount=float(state.get("refund_amount") or 0.0),
        plan=str(customer.get("plan") or "unknown"),
        past_refunds_90d=int(customer.get("past_refunds_90d") or 0),
        priority=str(triage.get("priority") or ""),
    )


def is_authorised(required: str, actual: Optional[str]) -> bool:
    """Is `actual` allowed to sign for a decision that requires `required`?

    The check exists because `Command(resume=...)` is not validated by LangGraph in any way (that
    was Wednesday's lesson). Whatever a caller passes arrives in the node as-is, which means the
    claim "I am a billing manager" arrives with exactly as much authority as the caller chose to
    give it. So the node asks this function rather than trusting the payload.

    Worth being honest with students about what this is and is not: it is an *authorisation* rule,
    not authentication. Nothing here proves the caller is who they say they are. In a real system
    the role comes from a signed session, not from a dict; what belongs in the graph either way is
    the rule about which role is sufficient.
    """
    if not required or required == NOBODY:
        return True
    return actual in _AUTHORISED.get(required, set())
