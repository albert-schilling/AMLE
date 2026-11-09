"""Week 10 Day 3: hooks that guard and witness tool calls, tested offline.

No API key and no network. The hook mechanism (`run_hooked`) is pure Python over a fake `execute`,
and the refund guard runs against plain dicts, so every branch is checkable with a stub. Two loop
integration tests patch the Anthropic SDK boundary (`scoutbot.loop._client`), the same pattern as
`tests/test_loop.py`, to prove the guard blocks a refund the *model* asked for.
"""
from types import SimpleNamespace
from unittest.mock import patch

from scoutbot.hooks import Hooks, audit_hook, refund_guard, run_hooked
from scoutbot.loop import run_agent_loop
from scoutbot.notify import Ledger
from scoutbot.tools import issue_refund, refund_key


# --- customers the guard looks up (billing facts, never model-supplied) ---
CUSTOMERS = {
    "clean": {"plan": "pro", "past_refunds_90d": 0},       # under every threshold
    "repeat": {"plan": "pro", "past_refunds_90d": 4},      # repeat refunder -> always needs a human
}


def _get_customer(customer_id):
    return CUSTOMERS.get(customer_id, {})


# ---------------------------------------------------------------------------
# The mechanism: run_hooked
# ---------------------------------------------------------------------------

def test_no_hooks_runs_the_tool_unwrapped():
    called = []

    def execute():
        called.append(True)
        return {"ok": True}

    assert run_hooked("any_tool", {}, execute, None) == {"ok": True}
    assert called == [True]


def test_a_pre_hook_can_block_and_the_tool_never_runs():
    ran = []

    def deny(name, args):
        return {"blocked": True}

    def execute():
        ran.append(True)
        return {"ok": True}

    obs = run_hooked("any_tool", {}, execute, Hooks(pre=[deny]))
    assert obs == {"blocked": True}
    assert ran == []  # the tool was never executed


def test_a_pre_hook_returning_none_allows_the_call():
    def allow(name, args):
        return None

    obs = run_hooked("any_tool", {"x": 1}, lambda: {"ok": True}, Hooks(pre=[allow]))
    assert obs == {"ok": True}


def test_post_hooks_witness_both_allowed_and_blocked_calls():
    trail = []
    hooks = Hooks(pre=[lambda n, a: {"blocked": True} if n == "bad" else None], post=[audit_hook(trail)])

    run_hooked("good", {"a": 1}, lambda: {"ok": True}, hooks)
    run_hooked("bad", {"a": 2}, lambda: {"ok": True}, hooks)

    assert [r["tool"] for r in trail] == ["good", "bad"]
    assert trail[0]["observation"] == {"ok": True}
    assert trail[1]["observation"] == {"blocked": True}  # the veto is recorded too


# ---------------------------------------------------------------------------
# The guard: refund_guard
# ---------------------------------------------------------------------------

def test_refund_guard_ignores_other_tools():
    guard = refund_guard(_get_customer, approve_fn=lambda r: False)
    assert guard("look_up_customer", {"customer_id": "clean"}) is None


def test_small_refund_on_a_clean_account_passes_without_approval():
    # Below AUTO_APPROVE_UNDER (50): no human needed, so no approval is even requested.
    guard = refund_guard(_get_customer, approve_fn=lambda r: False)
    assert guard("issue_refund", {"customer_id": "clean", "amount": 20}) is None


def test_large_refund_is_blocked_without_approval():
    guard = refund_guard(_get_customer, approve_fn=lambda reason: False)
    blocked = guard("issue_refund", {"customer_id": "clean", "amount": 900})
    assert blocked["issued"] is False
    assert blocked["blocked"] is True
    assert "billing_manager" in blocked["reason"]


def test_large_refund_passes_when_approved():
    guard = refund_guard(_get_customer, approve_fn=lambda reason: True)
    assert guard("issue_refund", {"customer_id": "clean", "amount": 900}) is None


def test_repeat_refunder_needs_a_human_even_for_a_tiny_amount():
    guard = refund_guard(_get_customer, approve_fn=lambda reason: False)
    blocked = guard("issue_refund", {"customer_id": "repeat", "amount": 5})
    assert blocked["blocked"] is True
    assert "refunds in the last 90 days" in blocked["reason"]


# ---------------------------------------------------------------------------
# The tool: issue_refund idempotency
# ---------------------------------------------------------------------------

def test_refund_key_is_stable_for_the_same_request():
    assert refund_key("1001", 900) == refund_key("1001", 900.0) == "1001:refund:900.00"
    assert refund_key("1001", 900) != refund_key("1001", 800)


def test_issue_refund_fires_once_then_dedupes():
    ledger = Ledger.in_memory()
    first = issue_refund("1001", 900, ledger=ledger)
    second = issue_refund("1001", 900, ledger=ledger)
    assert first["issued"] is True
    assert second["issued"] is False and second["skipped"] is True
    assert len(ledger.entries()) == 1  # the money moved once


# ---------------------------------------------------------------------------
# Loop integration: the guard blocks a refund the model asked for
# ---------------------------------------------------------------------------

def _text(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use(name, input_, tid="toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=tid)


def _response(*blocks):
    return SimpleNamespace(content=list(blocks))


@patch("scoutbot.loop._client")
def test_loop_blocks_an_unapproved_refund_via_the_guard(mock_client):
    mock_client.return_value.messages.create.side_effect = [
        _response(_text("Refunding the full amount."), _tool_use("issue_refund", {"customer_id": "clean", "amount": 900})),
        _response(_text("The refund needs a manager, so I've flagged it.")),
    ]
    trail = []
    hooks = Hooks(pre=[refund_guard(_get_customer, approve_fn=lambda r: False)], post=[audit_hook(trail)])

    result = run_agent_loop(
        "Please refund me EUR 900", customer_id="clean", ledger=Ledger.in_memory(), hooks=hooks
    )

    assert result.steps[0].action == "issue_refund"
    assert result.steps[0].observation["blocked"] is True
    assert trail[0]["tool"] == "issue_refund"  # the blocked attempt was audited


@patch("scoutbot.loop._client")
def test_loop_lets_an_approved_refund_through_and_records_it(mock_client):
    mock_client.return_value.messages.create.side_effect = [
        _response(_text("Refunding."), _tool_use("issue_refund", {"customer_id": "clean", "amount": 900})),
        _response(_text("Done - your refund is on its way.")),
    ]
    ledger = Ledger.in_memory()
    hooks = Hooks(pre=[refund_guard(_get_customer, approve_fn=lambda r: True)])

    result = run_agent_loop("Refund EUR 900", customer_id="clean", ledger=ledger, hooks=hooks)

    assert result.steps[0].observation["issued"] is True
    assert len(ledger.entries()) == 1


@patch("scoutbot.loop._client")
def test_refund_tool_is_not_offered_without_a_ledger(mock_client):
    # No ledger -> issue_refund is not in the tool list, so the model cannot move money at all.
    mock_client.return_value.messages.create.side_effect = [_response(_text("Nothing to do."))]
    run_agent_loop("hi", customer_id="clean")
    _, kwargs = mock_client.return_value.messages.create.call_args
    tool_names = {t["name"] for t in kwargs["tools"]}
    assert "issue_refund" not in tool_names
