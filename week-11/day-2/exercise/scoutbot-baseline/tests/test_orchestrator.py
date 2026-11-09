"""Week 11 Day 1: the orchestrator-worker team, tested offline.

No key, no network, no embedder. Three kinds of test, mirroring the day's three ideas:

- the **router and classifier are pure functions** - checked with a hand-made dict, no graph;
- each **worker subgraph** is invoked directly with a hand-made state and a stub collaborator; and
- the **whole orchestrator** routes a ticket end to end, with every collaborator stubbed.
"""
from types import SimpleNamespace

from scoutbot.orchestrator import (
    SPECIALTIES,
    build_order_worker,
    build_orchestrator,
    build_refund_worker,
    build_research_worker,
    build_supervisor,
    classify_specialty,
    dispatch_node,
    initial_state,
    look_up_customer_node,
    route_to_specialist,
)


# --- fakes -----------------------------------------------------------------

def _hit(source, text, score=0.9):
    return SimpleNamespace(source=source, ordinal=0, text=text, score=score)


class StubKB:
    """A knowledge base with a fixed hit list - no embedder, no SQLite."""

    def __init__(self, hits):
        self._hits = hits

    def search(self, query, *, k=3):
        return self._hits[:k]


CUSTOMERS = {
    "1001": {"found": True, "customer_id": "1001", "plan": "pro", "account_age_days": 430, "past_refunds_90d": 2},
    "1002": {"found": True, "customer_id": "1002", "plan": "free", "account_age_days": 12, "past_refunds_90d": 0},
}


def _get_customer(cid):
    return CUSTOMERS.get(cid, {"found": False, "customer_id": cid})


def _get_order(order_id):
    return {"found": True, "order_id": order_id.upper(), "status": "in_transit", "carrier": "DHL",
            "estimated_delivery": "2026-08-14"}


HITS = [_hit("refunds", "Refunds are issued within five business days.")]


# --- router + classifier are pure functions --------------------------------

def test_classify_specialty_routes_by_keyword():
    assert classify_specialty("I want a refund, I was charged twice") == "refund"
    assert classify_specialty("Where is my order ORD-1042?") == "order"
    assert classify_specialty("How do I export my data to CSV?") == "research"


def test_classify_specialty_refund_beats_order_when_both_present():
    # money is the action; the order is context
    assert classify_specialty("I was charged twice, and where is my order?") == "refund"


def test_route_to_specialist_is_a_pure_function():
    assert route_to_specialist({"specialty": "order"}) == "order"
    # falls back to research when dispatch never ran or wrote something unknown
    assert route_to_specialist({}) == "research"
    assert route_to_specialist({"specialty": "nonsense"}) == "research"


def test_dispatch_node_writes_specialty_and_logs():
    out = dispatch_node({"ticket_text": "please refund me"})
    assert out["specialty"] == "refund"
    assert out["transcript"] == ["dispatch->refund"]


def test_dispatch_node_accepts_an_injected_classifier():
    out = dispatch_node({"ticket_text": "anything"}, classify=lambda t: "order")
    assert out["specialty"] == "order"


def test_look_up_customer_node_uses_injected_getter():
    out = look_up_customer_node({"customer_id": "1001"}, get_customer=_get_customer)
    assert out["customer"]["plan"] == "pro"
    assert out["transcript"] == ["look_up_customer"]


# --- worker subgraphs, invoked directly ------------------------------------

def test_refund_worker_flags_a_big_refund_for_a_human():
    worker = build_refund_worker().compile()
    state = initial_state("T1", "refund me", "1001", refund_amount=900.0)
    state["customer"] = CUSTOMERS["1001"]
    out = worker.invoke(state)
    assert out["finding"]["needs_human"] is True          # investigate ran (wrote finding)
    assert out["finding"]["approver"] == "billing_manager"  # repeat refunder / big amount
    assert "needs sign-off" in out["answer"]               # respond ran (wrote answer)


def test_refund_worker_auto_approves_a_small_clean_refund():
    worker = build_refund_worker().compile()
    state = initial_state("T2", "small refund", "1002", refund_amount=12.5)
    state["customer"] = CUSTOMERS["1002"]
    out = worker.invoke(state)
    assert out["finding"]["needs_human"] is False
    assert "approved automatically" in out["answer"]


def test_order_worker_reports_status_via_injected_lookup():
    worker = build_order_worker(get_order_status=_get_order).compile()
    state = initial_state("T3", "Where is my order ORD-1042?", "1001")
    out = worker.invoke(state)
    assert out["finding"]["status"] == "in_transit"
    assert "ORD-1042" in out["answer"] and "in_transit" in out["answer"]


def test_order_worker_handles_a_missing_order_number():
    worker = build_order_worker(get_order_status=_get_order).compile()
    state = initial_state("T4", "Where is my package?", "1001")
    out = worker.invoke(state)
    assert out["finding"]["order_id"] is None
    assert "ORD-XXXX" in out["answer"]


def test_research_worker_grounds_in_retrieved_passages():
    worker = build_research_worker(kb=StubKB(HITS)).compile()
    state = initial_state("T5", "How long do refunds take?", "1001")
    out = worker.invoke(state)
    assert out["finding"]["passages"]        # investigate ran (retrieved passages)
    assert "five business days" in out["answer"]  # respond ran (grounded the answer)


def test_research_worker_declines_when_nothing_matches():
    worker = build_research_worker(kb=StubKB([])).compile()
    out = worker.invoke(initial_state("T6", "obscure question", "1001"))
    assert "route it to a person" in out["answer"]


# --- the whole orchestrator, end to end ------------------------------------

def _orchestrator():
    return build_orchestrator(get_customer=_get_customer, get_order_status=_get_order, kb=StubKB(HITS))


def test_orchestrator_routes_a_refund_ticket_through_the_refund_worker():
    out = _orchestrator().invoke(initial_state("T-1001", "I was charged twice, refund me", "1001", 900.0))
    assert out["specialty"] == "refund"
    assert "needs sign-off" in out["answer"]
    # the orchestration path is visible in the transcript, in order: the transcript logs routing, and
    # each worker is a black box (its internal investigate/respond steps stay inside the subgraph)
    assert out["transcript"] == ["look_up_customer", "dispatch->refund", "finalize"]


def test_orchestrator_routes_an_order_ticket_through_the_order_worker():
    out = _orchestrator().invoke(initial_state("T-1002", "Where is my order ORD-1042?", "1001"))
    assert out["specialty"] == "order"
    assert "in_transit" in out["answer"]
    assert out["transcript"][:2] == ["look_up_customer", "dispatch->order"]
    assert out["transcript"][-1] == "finalize"


def test_orchestrator_routes_a_research_ticket_through_the_research_worker():
    out = _orchestrator().invoke(initial_state("T-1003", "How do I export to CSV?", "1002"))
    assert out["specialty"] == "research"
    assert "Based on our policy" in out["answer"]


def test_orchestrator_shares_one_customer_lookup_with_the_worker():
    # look_up_customer runs once at the top; the refund worker reads the facts it wrote.
    out = _orchestrator().invoke(initial_state("T-1004", "refund me please", "1001", 900.0))
    assert out["customer"]["plan"] == "pro"  # fetched by the orchestrator, visible after the worker ran


# --- supervisor variant ----------------------------------------------------

def test_supervisor_consults_a_plan_of_specialists_in_turn():
    sup = build_supervisor(get_order_status=_get_order, kb=StubKB(HITS))
    state = initial_state("T-2001", "check policy then refund; order ORD-1042", "1001", 120.0)
    state["plan"] = ["research", "order", "refund"]
    out = sup.invoke(state)
    # each specialist was dispatched, and the supervisor closed out
    assert out["transcript"].count("supervisor->research") == 1
    assert out["transcript"].count("supervisor->order") == 1
    assert out["transcript"].count("supervisor->refund") == 1
    assert out["transcript"][-1] == "supervisor:done"


def test_specialties_constant_matches_the_workers():
    assert set(SPECIALTIES) == {"refund", "order", "research"}
    workers = build_orchestrator(get_customer=_get_customer, get_order_status=_get_order, kb=StubKB(HITS))
    # the compiled graph has a node per specialty
    assert set(SPECIALTIES).issubset(set(workers.get_graph().nodes))
