"""Week 11 Day 1: from one agent to a team - an orchestrator that dispatches to specialist workers.

For four weeks ScoutBot has been *one* agent: a single loop, or a single graph, that looks up the
customer, triages, retrieves, drafts, guards a refund, and sends - all of it driven by one prompt and
one state machine. That works, and Week 10 Day 5 wired every capability into one `resolve_ticket`. But
one agent doing everything has a ceiling: the prompt grows, the tools blur together, and a change to the
refund path risks the order path. The fix is the oldest one in engineering - **split the monolith into
specialists and put something in front of them to route the work.**

That "something in front" is the **orchestrator**, and each specialist is a **worker**. This module builds
the orchestrator-worker topology for real:

    START -> look_up_customer -> dispatch -> (refund | order | research) -> finalize -> END

- `look_up_customer` runs once, at the top, so every worker shares the same customer facts. This is the
  first thing to notice about multi-agent state: the workers are separate graphs, but they read and write
  the *same* `TeamState` keys, so a fact fetched once is visible to whichever specialist handles the ticket.
- `dispatch` classifies the ticket into a **specialty** (`refund`, `order`, or `research`) and writes it to
  state. It does no work itself; its whole job is to decide *who* works.
- `route_to_specialist` is the router - a plain function from state to a node name, testable with a
  hand-made dict and no graph at all (the same property Week 8 Day 2's routers had).
- Each worker is its own **subgraph**: a small two-node `StateGraph` (`investigate` then `respond`) compiled
  and dropped into the parent as a single node. A subgraph is the unit of encapsulation here - a worker can
  grow internal steps without the orchestrator knowing or caring.

Every worker reuses a piece ScoutBot already owns, so this day adds *topology*, not new capability:

- the **refund** worker reuses `policy.decide_approval` (the rules table - no model, no network);
- the **order** worker reuses an order-status lookup (the Day-1 MCP tool's job, here an injectable
  function defaulting to `mock_orders.json`);
- the **research** worker reuses `knowledge.KnowledgeBase.search` + `format_passages` (Week 9's retrieval).

And because each collaborator is injected (`get_customer`, `classify`, `get_order_status`, `kb`) exactly the
way `graph.py` injects `kb`/`classify`, the whole team runs offline in a test with stubs, no key and no
network - the discipline every week has kept.

The **supervisor** variant (`build_supervisor`) is included as the contrast topology: instead of a router
that picks one worker, a hub node hands out work from a `plan` list and each worker reports back to it, so
the team can consult several specialists in turn. Swarm - peer agents handing off to each other with no hub
- is named on the slides and deliberately not built today.
"""
import json
import operator
import re
from functools import partial
from pathlib import Path
from typing import Annotated, Callable, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .knowledge import KnowledgeBase, fastembed_embedder, format_passages
from .policy import decide_approval
from .tools import look_up_customer

ORDERS_PATH = Path(__file__).parent.parent.parent / "mock_orders.json"
CORPUS_DIR = Path(__file__).parent.parent.parent / "knowledge_base"

SPECIALTIES = ("refund", "order", "research")


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
class TeamState(TypedDict, total=False):
    """Everything the team accumulates for one ticket - one schema shared by orchestrator and workers.

    The workers are separate subgraphs, but they are *not* separate state. They read and write these same
    keys, which is what makes "one customer lookup, visible to whichever specialist runs" true rather than
    aspirational. Two kinds of field, the same split `graph.TicketState` teaches:

    - Plain fields (`customer`, `specialty`, `finding`, `answer`, the inputs) are last-write-wins.
    - `transcript` carries a reducer (`operator.add`), so each node *appends* the step it ran instead of
      overwriting the log. Without the annotation, a later node would silently erase the earlier steps -
      the same first-graph mistake `notes` guards against in Week 8.

    **`transcript` is written only at the orchestrator level (`look_up_customer`, `dispatch`, `finalize`,
    and the `supervisor`), never inside a worker subgraph.** That is deliberate, and it is a multi-agent
    state subtlety worth knowing: a compiled subgraph *shares* this channel with its parent, and when a
    subgraph node writes to a reducer channel the parent has already accumulated into, the parent re-reduces
    the subgraph's whole channel value and the earlier steps get counted twice. Keeping the accumulator at
    one level sidesteps that entirely and reads as clean encapsulation: the transcript shows *which
    specialist handled the ticket* (`dispatch->refund`), and each worker is a black box tested on its own
    (`finding` proves `investigate` ran, `answer` proves `respond` ran). Workers therefore write only the
    plain `finding`/`answer` channels, which are last-write-wins and never double-count.

    `finding` is the hand-off *inside* a worker subgraph: the `investigate` node writes what it learned, the
    `respond` node reads it and composes the answer. `plan` is used only by the supervisor variant; the
    orchestrator path ignores it.
    """

    ticket_id: str
    ticket_text: str
    customer_id: str
    refund_amount: float
    customer: dict
    specialty: str
    plan: list
    finding: dict
    transcript: Annotated[list, operator.add]
    answer: str


class WorkerState(TypedDict, total=False):
    """The slice of state a worker subgraph reads and writes - deliberately *without* `transcript`.

    A worker shares state with the parent by key name, so it must not declare the parent's reducer channel:
    a compiled subgraph re-emits every channel it holds, and a re-emitted `operator.add` channel would be
    added to the parent's copy a second time (the double-count described on `TeamState.transcript`). Workers
    therefore own only plain, last-write-wins channels - the ticket facts they read (`ticket_text`,
    `customer`, `refund_amount`), the intra-worker hand-off (`finding`), and the result (`answer`). All five
    also exist on `TeamState`, which is exactly what lets a worker drop into the orchestrator as one node and
    share those facts, while the transcript stays the orchestrator's to keep.
    """

    ticket_text: str
    customer: dict
    refund_amount: float
    finding: dict
    answer: str


# ---------------------------------------------------------------------------
# Orchestrator nodes
# ---------------------------------------------------------------------------
def look_up_customer_node(state: TeamState, get_customer: Callable[[str], dict] = look_up_customer) -> dict:
    """Fetch the customer once, at the top, so every worker shares the facts.

    `get_customer` is injected (defaults to the real `tools.look_up_customer`); a test passes a dict-backed
    stub, so the orchestrator runs with no file and no network.
    """
    customer = get_customer(state["customer_id"])
    return {"customer": customer, "transcript": ["look_up_customer"]}


REFUND_HINTS = ("refund", "charged", "charge", "billed", "overcharged", "double-charged", "money back")
ORDER_HINTS = ("order", "ord-", "delivery", "delivered", "shipped", "shipping", "tracking", "package", "parcel", "arrive")


def classify_specialty(text: str) -> str:
    """Decide which specialist a ticket belongs to - a plain keyword rule, no model.

    Order matters: a ticket that mentions both a charge and an order (e.g. "I was charged twice, and where
    is my order?") is a *refund* first, because the money is the action and the order is context. `research`
    is the safe default - a how-to, a policy question, or an account change routes to the specialist that
    reads the knowledge base rather than the one that moves money.

    Deliberately deterministic and injectable (see `dispatch_node`'s `classify` argument): the point of the
    day is the *topology*, so the dispatcher stays a rule you can read and test. Using the model to classify
    is a one-line swap (and Tuesday's planner does exactly that) - it is listed as an "if you finish early".
    """
    low = text.lower()
    if any(h in low for h in REFUND_HINTS):
        return "refund"
    if any(h in low for h in ORDER_HINTS):
        return "order"
    return "research"


def dispatch_node(state: TeamState, classify: Optional[Callable[[str], str]] = None) -> dict:
    """Decide *who* works, and write it to state. Does no ticket work itself.

    `classify` defaults to the keyword `classify_specialty`; inject a model-backed classifier to make the
    dispatcher smarter without touching the routing.
    """
    classify = classify or classify_specialty
    specialty = classify(state["ticket_text"])
    return {"specialty": specialty, "transcript": [f"dispatch->{specialty}"]}


def route_to_specialist(state: TeamState) -> str:
    """The router: state -> the name of the worker node to run next.

    A pure function of state, so it is unit-testable with a hand-made dict and no graph - the single most
    reused testing property in this curriculum. Falls back to `research` if dispatch never ran.
    """
    specialty = state.get("specialty") or "research"
    return specialty if specialty in SPECIALTIES else "research"


def finalize_node(state: TeamState) -> dict:
    """Join point for every worker: one place the run ends, whichever specialist handled it.

    Mirrors the Day-4 graph's `send_reply` diamond - both branches rejoin at one node - so anything that
    must happen once per ticket (here just closing the transcript) is written once, not per worker.
    """
    return {"transcript": ["finalize"]}


# ---------------------------------------------------------------------------
# Worker: refund specialist  (reuses policy.decide_approval)
# ---------------------------------------------------------------------------
def refund_investigate(state: WorkerState) -> dict:
    """Apply the refund policy table to this ticket's facts. No model, no network - just the rules."""
    customer = state.get("customer") or {}
    amount = float(state.get("refund_amount") or 0.0)
    appr = decide_approval(
        amount=amount,
        plan=str(customer.get("plan") or "unknown"),
        past_refunds_90d=int(customer.get("past_refunds_90d") or 0),
        priority="",
    )
    finding = {
        "amount": amount,
        "needs_human": appr.needs_human,
        "approver": appr.approver,
        "reason": appr.reason,
    }
    return {"finding": finding}


def refund_respond(state: WorkerState) -> dict:
    """Turn the policy finding into the customer-facing answer."""
    f = state.get("finding") or {}
    amount = f.get("amount", 0.0)
    if f.get("needs_human"):
        answer = (
            f"A refund of EUR {amount:.2f} needs sign-off from the {f['approver']}: {f['reason']}. "
            "I've routed it for approval."
        )
    else:
        answer = f"A refund of EUR {amount:.2f} is approved automatically: {f['reason']}."
    return {"answer": answer}


def build_refund_worker() -> StateGraph:
    """The refund specialist as its own two-node subgraph: investigate (apply policy) then respond."""
    b = StateGraph(WorkerState)
    b.add_node("refund_investigate", refund_investigate)
    b.add_node("refund_respond", refund_respond)
    b.add_edge(START, "refund_investigate")
    b.add_edge("refund_investigate", "refund_respond")
    b.add_edge("refund_respond", END)
    return b


# ---------------------------------------------------------------------------
# Worker: order specialist  (reuses an order-status lookup - the Day-1 MCP tool's job)
# ---------------------------------------------------------------------------
_ORDER_ID_RE = re.compile(r"ORD-\d+", re.IGNORECASE)


def _default_order_lookup(order_id: str) -> dict:
    """Read one order's status from `mock_orders.json` (stands in for the MCP `get_order_status` tool)."""
    orders = json.loads(ORDERS_PATH.read_text())
    record = orders.get(order_id.upper())
    if record is None:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id.upper(), **record}


def order_investigate(state: WorkerState, get_order_status: Callable[[str], dict] = _default_order_lookup) -> dict:
    """Pull the order id out of the ticket and look up its status.

    `get_order_status` is injected (defaults to the local mock); a real ScoutBot passes the Day-1 MCP
    provider's `call`, and a test passes a stub - the order worker never has to know which.
    """
    match = _ORDER_ID_RE.search(state.get("ticket_text") or "")
    if match is None:
        return {"finding": {"found": False, "order_id": None}}
    status = get_order_status(match.group(0))
    return {"finding": status}


def order_respond(state: WorkerState) -> dict:
    """Compose the answer from the order finding."""
    f = state.get("finding") or {}
    if not f.get("order_id"):
        answer = "I couldn't find an order number in your message. Could you share the ORD-XXXX id?"
    elif not f.get("found"):
        answer = f"I couldn't find order {f['order_id']} on the account. Can you double-check the number?"
    else:
        answer = f"Order {f['order_id']} is currently {f.get('status', 'unknown')}"
        if f.get("carrier"):
            answer += f" with {f['carrier']}"
        if f.get("estimated_delivery"):
            answer += f", estimated delivery {f['estimated_delivery']}"
        answer += "."
    return {"answer": answer}


def build_order_worker(get_order_status: Callable[[str], dict] = _default_order_lookup) -> StateGraph:
    """The order specialist as a two-node subgraph: investigate (look up status) then respond."""
    b = StateGraph(WorkerState)
    b.add_node("order_investigate", partial(order_investigate, get_order_status=get_order_status))
    b.add_node("order_respond", order_respond)
    b.add_edge(START, "order_investigate")
    b.add_edge("order_investigate", "order_respond")
    b.add_edge("order_respond", END)
    return b


# ---------------------------------------------------------------------------
# Worker: research specialist  (reuses Week 9 retrieval)
# ---------------------------------------------------------------------------
_PROCESS_KB: Optional[KnowledgeBase] = None


def _process_kb() -> KnowledgeBase:
    """One lazily-built knowledge base per process (mirrors `graph._process_kb`).

    The `fastembed_embedder()` call is the only line here that touches the network, and only on the very
    first build in a machine's life. Every test injects a stub `kb` instead, so the suite never downloads a
    model to check the wiring.
    """
    global _PROCESS_KB
    if _PROCESS_KB is None:
        _PROCESS_KB = KnowledgeBase.build(CORPUS_DIR, fastembed_embedder())
    return _PROCESS_KB


def research_investigate(state: WorkerState, kb: Optional[KnowledgeBase] = None) -> dict:
    """Search the policy corpus for passages relevant to the ticket.

    `kb` is injected (defaults to the lazy process store); a test passes a stub with a fixed hit list, so
    research runs with no embedder and no network.
    """
    kb = kb if kb is not None else _process_kb()
    hits = kb.search(state.get("ticket_text") or "", k=3)
    passages = [{"source": h.source, "text": h.text} for h in hits]
    return {"finding": {"passages": passages}}


def research_respond(state: WorkerState) -> dict:
    """Ground an answer in the retrieved passages, or decline if nothing matched."""
    passages = (state.get("finding") or {}).get("passages") or []
    if not passages:
        answer = "I couldn't find anything in our policy docs about that. Let me route it to a person."
    else:
        answer = "Based on our policy:\n" + format_passages(passages)
    return {"answer": answer}


def build_research_worker(kb: Optional[KnowledgeBase] = None) -> StateGraph:
    """The research specialist as a two-node subgraph: investigate (retrieve) then respond."""
    b = StateGraph(WorkerState)
    b.add_node("research_investigate", partial(research_investigate, kb=kb))
    b.add_node("research_respond", research_respond)
    b.add_edge(START, "research_investigate")
    b.add_edge("research_investigate", "research_respond")
    b.add_edge("research_respond", END)
    return b


# ---------------------------------------------------------------------------
# Orchestrator (orchestrator-worker topology)
# ---------------------------------------------------------------------------
def build_workers(
    get_order_status: Callable[[str], dict] = _default_order_lookup,
    kb: Optional[KnowledgeBase] = None,
) -> dict:
    """Compile the three specialist subgraphs, each with its collaborator injected."""
    return {
        "refund": build_refund_worker().compile(),
        "order": build_order_worker(get_order_status=get_order_status).compile(),
        "research": build_research_worker(kb=kb).compile(),
    }


def orchestrator_builder(
    get_customer: Callable[[str], dict] = look_up_customer,
    classify: Optional[Callable[[str], str]] = None,
    get_order_status: Callable[[str], dict] = _default_order_lookup,
    kb: Optional[KnowledgeBase] = None,
) -> StateGraph:
    """The orchestrator-worker graph, un-compiled.

        START -> look_up_customer -> dispatch -> (refund | order | research) -> finalize -> END

    The three workers are compiled subgraphs added as single nodes; `add_conditional_edges` on `dispatch`
    sends the run to exactly one of them via `route_to_specialist`, and all three rejoin at `finalize`.
    Every collaborator is injected so the whole graph runs offline in a test.
    """
    workers = build_workers(get_order_status=get_order_status, kb=kb)
    b = StateGraph(TeamState)
    b.add_node("look_up_customer", partial(look_up_customer_node, get_customer=get_customer))
    b.add_node("dispatch", partial(dispatch_node, classify=classify))
    for name in SPECIALTIES:
        b.add_node(name, workers[name])
    b.add_node("finalize", finalize_node)

    b.add_edge(START, "look_up_customer")
    b.add_edge("look_up_customer", "dispatch")
    b.add_conditional_edges(
        "dispatch",
        route_to_specialist,
        {name: name for name in SPECIALTIES},
    )
    for name in SPECIALTIES:
        b.add_edge(name, "finalize")
    b.add_edge("finalize", END)
    return b


def build_orchestrator(**kwargs):
    """Compile the orchestrator-worker graph. See `orchestrator_builder` for the injectable collaborators."""
    return orchestrator_builder(**kwargs).compile()


def initial_state(ticket_id: str, ticket_text: str, customer_id: str, refund_amount: float = 0.0) -> TeamState:
    """A full initial state, so a printed run shows every declared field from the first line."""
    return {
        "ticket_id": ticket_id,
        "ticket_text": ticket_text,
        "customer_id": customer_id,
        "refund_amount": refund_amount,
        "customer": {},
        "specialty": "",
        "plan": [],
        "finding": {},
        "transcript": [],
        "answer": "",
    }


# ---------------------------------------------------------------------------
# Supervisor variant (the contrast topology)
# ---------------------------------------------------------------------------
def supervisor_node(state: TeamState) -> Command:
    """A hub that hands out work from a `plan` list and loops until it is empty.

    The difference from the orchestrator's router in one line: the router picks *one* worker and the run is
    over; the supervisor consults workers *in turn* and each reports back here, so a ticket can visit several
    specialists. It steers with `Command(goto=..., update=...)` rather than a conditional edge - the node
    itself decides the next hop, which is why a supervisor graph needs no `add_conditional_edges`.
    """
    plan = list(state.get("plan") or [])
    if plan:
        nxt, rest = plan[0], plan[1:]
        return Command(goto=nxt, update={"plan": rest, "transcript": [f"supervisor->{nxt}"]})
    return Command(goto=END, update={"transcript": ["supervisor:done"]})


def build_supervisor(
    get_order_status: Callable[[str], dict] = _default_order_lookup,
    kb: Optional[KnowledgeBase] = None,
):
    """The supervisor topology over the same three worker subgraphs.

    Wiring difference from the orchestrator: each worker's edge goes back to `supervisor` (report back), not
    to a single `finalize`, and the supervisor loops on `plan` until it is spent. Seed `plan` with the list
    of specialists to consult (e.g. `["research", "refund"]` for "check the policy, then handle the refund").
    """
    workers = build_workers(get_order_status=get_order_status, kb=kb)
    b = StateGraph(TeamState)
    b.add_node("look_up_customer", look_up_customer_node)
    b.add_node("supervisor", supervisor_node)
    for name in SPECIALTIES:
        b.add_node(name, workers[name])
        b.add_edge(name, "supervisor")
    b.add_edge(START, "look_up_customer")
    b.add_edge("look_up_customer", "supervisor")
    return b.compile()
