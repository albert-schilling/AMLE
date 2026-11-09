"""The approval policy, tested exhaustively, with no graph, no mock, no API key and no network.

This file is the argument for keeping `policy.py` pure, and it is worth showing to students before
they write any of it. Every business rule the day introduces is checked here, the whole file runs in
milliseconds, and there is nothing in it that could fail for a reason unrelated to the policy.

Compare that with what it would take to test the same rules if they lived inside a prompt: a live
model call per case, a bill, a flake rate, and no way to prove the rule holds rather than merely
that it held once. The rules that decide who may authorise a nine-hundred-euro refund are exactly
the rules that deserve the cheap, exhaustive test.

The parametrised case list doubles as documentation: it is the approval table, written out.
"""
import pytest

from scoutbot.policy import (
    AUTO_APPROVE_UNDER,
    BILLING_MANAGER,
    LEAD_APPROVES_UNDER,
    NOBODY,
    REPEAT_REFUND_THRESHOLD,
    SUPPORT_LEAD,
    approval_for_state,
    decide_approval,
    is_authorised,
)


@pytest.mark.parametrize(
    "amount, past_refunds, priority, expected_human, expected_approver",
    [
        # Under every threshold, on a clean account: ScoutBot answers it itself.
        (0.0, 0, "low", False, NOBODY),
        (12.5, 0, "medium", False, NOBODY),
        (49.99, 0, "low", False, NOBODY),
        # At the first threshold a support lead is pulled in. Note the boundary is inclusive.
        (50.0, 0, "low", True, SUPPORT_LEAD),
        (499.99, 0, "low", True, SUPPORT_LEAD),
        # At the second, a billing manager.
        (500.0, 0, "low", True, BILLING_MANAGER),
        (900.0, 2, "high", True, BILLING_MANAGER),
        # Refund history outranks the amount entirely: small money, established pattern.
        (12.5, REPEAT_REFUND_THRESHOLD, "low", True, BILLING_MANAGER),
        (0.0, 4, "low", True, BILLING_MANAGER),
        # No money at all, but the model judged it urgent, so a person still sees it.
        (0.0, 0, "high", True, SUPPORT_LEAD),
    ],
)
def test_the_approval_table(amount, past_refunds, priority, expected_human, expected_approver):
    decision = decide_approval(
        amount=amount, plan="pro", past_refunds_90d=past_refunds, priority=priority
    )

    assert decision.needs_human is expected_human
    assert decision.approver == expected_approver


def test_every_decision_explains_itself():
    """A decision a human cannot understand is one they cannot challenge, so `reason` is not
    decoration: it goes into the pause payload and tells the approver which rule pulled them in."""
    for amount, refunds, priority in [(900.0, 0, "low"), (0.0, 5, "low"), (0.0, 0, "high")]:
        decision = decide_approval(
            amount=amount, plan="pro", past_refunds_90d=refunds, priority=priority
        )
        assert decision.reason
        assert decision.reason == decision.reason.strip()


def test_the_boundaries_are_where_the_constants_say_they_are():
    """Thresholds are inclusive at the bottom, which is the kind of detail worth pinning down in a
    test rather than leaving to whoever reads the `>=` next."""
    just_under = decide_approval(
        amount=AUTO_APPROVE_UNDER - 0.01, plan="free", past_refunds_90d=0, priority="low"
    )
    exactly_at = decide_approval(
        amount=AUTO_APPROVE_UNDER, plan="free", past_refunds_90d=0, priority="low"
    )

    assert just_under.needs_human is False
    assert exactly_at.needs_human is True
    assert exactly_at.approver == SUPPORT_LEAD

    assert (
        decide_approval(
            amount=LEAD_APPROVES_UNDER, plan="free", past_refunds_90d=0, priority="low"
        ).approver
        == BILLING_MANAGER
    )


def test_the_route_follows_from_the_decision():
    """`Approval.route` is what keeps the router a one-liner."""
    assert decide_approval(900.0, "pro", 0, "low").route == "escalate"
    assert decide_approval(1.0, "pro", 0, "low").route == "auto_approve"


# --- Reading the decision off a run's state -------------------------------------------------


def test_approval_for_state_unpacks_the_facts_it_needs():
    state = {
        "refund_amount": 900.0,
        "customer": {"plan": "pro", "past_refunds_90d": 1},
        "triage": {"priority": "high"},
    }

    decision = approval_for_state(state)

    assert decision.approver == BILLING_MANAGER
    assert "900.00" in decision.reason


def test_a_half_built_state_cannot_cross_a_threshold_by_accident():
    """Defaults are chosen so a missing fact is worth nothing rather than worth everything. A
    state with no amount, no customer and no triage is not an error here, it is a zero-euro ticket
    nobody needs to see - which is the safe direction for the mistake to fall."""
    decision = approval_for_state({})

    assert decision.needs_human is False
    assert decision.approver == NOBODY


def test_a_string_amount_does_not_silently_disable_the_policy():
    """JSON and form input both hand over numbers as strings sooner or later, and `"900" >= 500`
    raises in Python 3 rather than comparing. Coercion happens once, here, so no caller has to
    remember."""
    decision = approval_for_state({"refund_amount": "900.0", "customer": {}, "triage": {}})

    assert decision.approver == BILLING_MANAGER


# --- Who may sign for whom ------------------------------------------------------------------


@pytest.mark.parametrize(
    "required, actual, expected",
    [
        (SUPPORT_LEAD, SUPPORT_LEAD, True),
        # A billing manager outranks a support lead, so they can sign either.
        (SUPPORT_LEAD, BILLING_MANAGER, True),
        # But not the other way around, which is the whole reason this function exists.
        (BILLING_MANAGER, SUPPORT_LEAD, False),
        (BILLING_MANAGER, BILLING_MANAGER, True),
        # Anything unrecognised is refused rather than waved through.
        (BILLING_MANAGER, "intern", False),
        (SUPPORT_LEAD, None, False),
        (SUPPORT_LEAD, "", False),
        # And a decision that needed nobody cannot be un-approved by a missing role.
        (NOBODY, None, True),
        ("", None, True),
    ],
)
def test_is_authorised(required, actual, expected):
    assert is_authorised(required, actual) is expected


def test_authorisation_is_not_authentication():
    """Worth one test as a comment that cannot rot: this function decides whether a *claimed* role
    is sufficient. Nothing here proves the claim. In a real system the role arrives from a signed
    session; what belongs in the graph either way is the rule about which role is enough."""
    assert is_authorised(BILLING_MANAGER, BILLING_MANAGER) is True
