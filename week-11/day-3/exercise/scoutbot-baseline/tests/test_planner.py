"""Week 11 Day 2, Topic 1: the model-backed planner and the planning team, tested offline.

Four kinds of test, mirroring the day:

- `_parse_plan` is a **pure function** over a fake response - ordered, filtered, with a safe fallback;
- `plan_ticket` is driven through the **patched `_client` seam** (same trick as `core.triage`), so the
  one model call is faked and the run touches no network - and it meters the call;
- `planner_node` runs with an **injected `make_plan`** stub, no model at all; and
- `build_planning_team` runs a **multi-step ticket end to end**, proving the planner feeds the Day-1
  supervisor which then consults each specialist in turn.
"""
from types import SimpleNamespace
from unittest import mock

from anthropic.types import Usage

from scoutbot.metering import Meter
from scoutbot.planner import (
    assess_difficulty,
    build_planning_team,
    plan_ticket,
    planner_node,
    _parse_plan,
)


# --- fakes -----------------------------------------------------------------

def _plan_response(steps, in_tok=900, out_tok=40):
    """A fake Anthropic response carrying a single make_plan tool call and a real Usage object."""
    block = SimpleNamespace(type="tool_use", name="make_plan", input={"steps": steps})
    return SimpleNamespace(content=[block], usage=Usage(input_tokens=in_tok, output_tokens=out_tok))


def _hit(source, text, score=0.9):
    return SimpleNamespace(source=source, ordinal=0, text=text, score=score)


class StubKB:
    def __init__(self, hits):
        self._hits = hits

    def search(self, query, *, k=3):
        return self._hits[:k]


CUSTOMERS = {
    "1001": {"found": True, "customer_id": "1001", "plan": "pro", "account_age_days": 430, "past_refunds_90d": 2},
}


def _get_customer(cid):
    return CUSTOMERS.get(cid, {"found": False, "customer_id": cid})


def _get_order(order_id):
    return {"found": True, "order_id": order_id.upper(), "status": "in_transit", "carrier": "DHL",
            "estimated_delivery": "2026-08-14"}


HITS = [_hit("refunds", "Refunds are issued within five business days.")]


# --- _parse_plan is a pure function ----------------------------------------

def test_parse_plan_keeps_order_and_valid_specialties():
    resp = _plan_response(["research", "refund"])
    assert _parse_plan(resp) == ["research", "refund"]


def test_parse_plan_drops_unknown_specialties():
    resp = _plan_response(["research", "astrology", "refund"])
    assert _parse_plan(resp) == ["research", "refund"]


def test_parse_plan_falls_back_to_research_when_empty():
    assert _parse_plan(_plan_response([])) == ["research"]


def test_parse_plan_falls_back_when_no_tool_call():
    resp = SimpleNamespace(content=[SimpleNamespace(type="text", text="I refuse")], usage=Usage(input_tokens=1, output_tokens=1))
    assert _parse_plan(resp) == ["research"]


# --- plan_ticket through the patched client seam ---------------------------

def test_plan_ticket_returns_the_models_ordered_plan():
    with mock.patch("scoutbot.planner._client") as client:
        client.return_value.messages.create.return_value = _plan_response(["research", "refund"])
        plan = plan_ticket("check the refund policy, then refund me", model="claude-haiku-4-5")
    assert plan == ["research", "refund"]


def test_plan_ticket_records_cost_and_latency_on_the_meter():
    meter = Meter()
    with mock.patch("scoutbot.planner._client") as client:
        client.return_value.messages.create.return_value = _plan_response(["order"], in_tok=500, out_tok=12)
        plan_ticket("where is ORD-1042", model="claude-haiku-4-5", meter=meter)
    assert len(meter.calls) == 1
    rec = meter.calls[0]
    assert rec.label == "plan" and rec.model == "claude-haiku-4-5"
    assert rec.input_tokens == 500 and rec.output_tokens == 12
    assert rec.cost_usd > 0 and rec.latency_ms >= 0


def test_plan_ticket_uses_the_tier_from_difficulty_when_no_model_given():
    # a genuinely multi-part ticket should plan on the strong tier by default
    hard = "First check the refund policy, and then refund me, and also where is my order ORD-1042?"
    captured = {}
    with mock.patch("scoutbot.planner._client") as client:
        def _create(**kwargs):
            captured["model"] = kwargs["model"]
            return _plan_response(["research", "refund", "order"])
        client.return_value.messages.create.side_effect = _create
        plan_ticket(hard)
    assert captured["model"] == "claude-sonnet-5"


def test_plan_ticket_plans_a_simple_ticket_on_the_cheap_tier():
    captured = {}
    with mock.patch("scoutbot.planner._client") as client:
        def _create(**kwargs):
            captured["model"] = kwargs["model"]
            return _plan_response(["research"])
        client.return_value.messages.create.side_effect = _create
        plan_ticket("How long do refunds take?")
    assert captured["model"] == "claude-haiku-4-5"


# --- assess_difficulty heuristic -------------------------------------------

def test_assess_difficulty_flags_multi_intent_tickets_as_hard():
    assert assess_difficulty("First check the policy, then refund my charge, and where is order ORD-1042?") == "hard"


def test_assess_difficulty_calls_a_one_liner_easy():
    assert assess_difficulty("How long do refunds take?") == "easy"


# --- planner_node with an injected stub (no model) -------------------------

def test_planner_node_uses_injected_make_plan_and_logs_the_plan():
    out = planner_node({"ticket_text": "anything"}, make_plan=lambda text: ["research", "refund"])
    assert out["plan"] == ["research", "refund"]
    assert out["transcript"] == ["planner->research+refund"]


# --- the whole planning team, end to end (planner -> supervisor) -----------

def _team(make_plan):
    return build_planning_team(
        get_customer=_get_customer,
        make_plan=make_plan,
        get_order_status=_get_order,
        kb=StubKB(HITS),
    )


def test_planning_team_runs_a_multi_step_plan_through_the_supervisor():
    # the planner (stubbed) produces a two-step plan; the Day-1 supervisor must consult both in order
    team = _team(lambda text: ["research", "refund"])
    from scoutbot.orchestrator import initial_state
    out = team.invoke(initial_state("T-3001", "check refund policy then refund me", "1001", 120.0))
    assert out["transcript"][0] == "look_up_customer"
    assert out["transcript"][1] == "planner->research+refund"
    assert out["transcript"].count("supervisor->research") == 1
    assert out["transcript"].count("supervisor->refund") == 1
    assert out["transcript"][-1] == "supervisor:done"
    assert out["answer"]  # a worker wrote a customer-facing answer


def test_planning_team_shares_one_customer_lookup_before_planning():
    team = _team(lambda text: ["refund"])
    from scoutbot.orchestrator import initial_state
    out = team.invoke(initial_state("T-3002", "refund me", "1001", 900.0))
    assert out["customer"]["plan"] == "pro"
    assert "needs sign-off" in out["answer"]  # pro repeat-refunder, big amount -> human sign-off
