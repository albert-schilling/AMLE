"""Week 11 Day 2, Topic 1: a model-backed planner that writes the plan the supervisor executes.

Day 1 built two topologies. The **orchestrator** used a keyword `dispatch` to pick *one* worker. The
**supervisor** was the richer one: a hub that reads an ordered `plan` list and consults each specialist
in turn - but Day 1 *seeded that plan by hand* (`initial_state(..., plan=["research", "refund"])`). That
was the honest gap left for today, called out in `orchestrator.classify_specialty`'s docstring: "using
the model to classify is a one-line swap, and Tuesday's planner does exactly that."

This module closes it. `plan_ticket` reads a ticket and asks the model for the *ordered list of
specialists* needed - `["research", "refund"]` for "check the refund policy, then refund me" - via a
single `make_plan` tool call. That list is exactly the `plan` `orchestrator.supervisor_node` already
consumes, so today's change is small and precise: **the supervisor stops being hand-seeded and gets a
real planner in front of it.** `build_planning_team` wires it up:

    START -> look_up_customer -> planner -> supervisor <-> (refund | order | research) -> END

Two design lines worth stating so the scope stays honest:

- This is a **planner**, not a plan-and-execute-with-replanning engine. It plans once, up front; it does
  not watch a worker fail and re-plan. That loop is real and worth knowing, but it is capstone scale;
  today's lesson is "the dispatcher can be a model, and its output is a plan a supervisor runs."
- The planner is the day's **cost lever in miniature**. It is a real model call - so unlike Day 1 it needs
  a key - but a *cheap* one by default (`metering.pick_model`), and it is metered like everything else. A
  multi-part ticket earns the strong tier; a one-line question does not. That is tiering applied to the
  very first call in the run.

Offline the same way every model call in this codebase is: the SDK boundary is `planner._client`, which
a test patches (exactly like `core._client`), so the planner, the node, and the whole team run with no
key and no network in the suite - collaborators (`make_plan`, `kb`, `get_order_status`) are all injected.
"""
import os
from functools import partial
from typing import Callable, List, Optional

from anthropic import Anthropic
from langgraph.graph import END, START, StateGraph

from .knowledge import KnowledgeBase
from .metering import Meter, measure, pick_model
from .orchestrator import (
    SPECIALTIES,
    TeamState,
    _default_order_lookup,
    build_workers,
    look_up_customer_node,
    supervisor_node,
)
from .tools import look_up_customer

# An explicit override wins over tiering; leave it unset to let `pick_model` choose per ticket.
PLAN_MODEL = os.environ.get("ANTHROPIC_PLAN_MODEL")

MAKE_PLAN_TOOL = {
    "name": "make_plan",
    "description": (
        "Record the ordered list of specialists needed to resolve this support ticket. List each "
        "specialist once, in the order they should act. Use only the specialists that are actually "
        "needed - most tickets need exactly one."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {"type": "string", "enum": list(SPECIALTIES)},
                "description": "Ordered specialists to consult: refund, order, and/or research.",
            }
        },
        "required": ["steps"],
    },
}

PLANNER_SYSTEM = (
    "You plan how a support team should resolve one customer ticket. Call make_plan exactly once "
    "with the ordered list of specialists to consult:\n"
    "- refund: anything about money - a charge, a refund, a billing dispute.\n"
    "- order: the status or whereabouts of a specific order (an ORD-XXXX id).\n"
    "- research: a policy or how-to question answered from the knowledge base.\n"
    "Order matters: if the customer wants you to check a policy *before* acting, put research first. "
    "Most tickets need exactly one specialist; use more only when the ticket genuinely asks for more. "
    "If a ticket needs a policy check and then a refund, the plan is research then refund."
)


class PlannerError(RuntimeError):
    """Raised when the planner cannot produce any usable plan. Callers fall back to `["research"]`
    rather than surfacing this, but it exists so a failure is nameable rather than a bare guess."""


def _client() -> Anthropic:
    """The SDK boundary tests patch - identical seam to `core._client`. Reads `ANTHROPIC_API_KEY`
    from the environment; nothing here hardcodes it."""
    return Anthropic()


def assess_difficulty(ticket_text: str) -> str:
    """A cheap, deterministic guess at whether a ticket earns the strong planner tier.

    Deliberately a heuristic, not a model call: spending a model call to decide whether to spend a
    model call is the tail wagging the dog. A ticket is `hard` when it looks genuinely multi-part -
    it is long, or it names more than one kind of work (a charge *and* an order), or it explicitly
    sequences steps ("first...", "then...", "after that..."). Everything else is `easy` and plans on
    the cheap tier. Callers can always override the model directly; this is only the default.
    """
    low = ticket_text.lower()
    signals = 0
    if len(ticket_text) > 220:
        signals += 1
    if any(w in low for w in (" then ", "after that", "first ", "also", "as well as", " and then ")):
        signals += 1
    money = any(w in low for w in ("refund", "charge", "charged", "billed", "money back"))
    order = any(w in low for w in ("order ", "ord-", "delivery", "tracking", "shipped"))
    policy = any(w in low for w in ("policy", "how do i", "how long", "can i", "am i able"))
    if (money + order + policy) >= 2:
        signals += 1
    return "hard" if signals >= 2 else "easy"


def _parse_plan(response) -> List[str]:
    """Pull the ordered plan out of a `make_plan` tool call, keeping only real specialties, in order.

    Defensive on purpose. The tool schema constrains `steps` to the three specialty names, but a model
    can still return an empty list, a duplicate, or - if `tool_choice` were ever relaxed - no tool call
    at all. Unknown values are dropped, order and (intentional) repeats are preserved, and an empty
    result falls back to `["research"]`: the same safe default the router uses, because the specialist
    that reads the knowledge base is the least-harmful place to send an unclassifiable ticket.
    """
    tool_uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
    if not tool_uses:
        return ["research"]
    steps = [s for s in (tool_uses[0].input or {}).get("steps", []) if s in SPECIALTIES]
    return steps or ["research"]


def plan_ticket(
    ticket_text: str,
    *,
    model: Optional[str] = None,
    meter: Optional[Meter] = None,
) -> List[str]:
    """Ask the model for the ordered list of specialists this ticket needs.

    The one model call the planner makes, and the one that replaces Day 1's keyword `classify_specialty`.
    `tool_choice` forces the `make_plan` call so the reply is always structured, and `_parse_plan`
    guarantees the return is a non-empty list of valid specialties, so the supervisor never has to
    validate it.

    **Model choice is the tiering lever.** With no `model` argument it uses `ANTHROPIC_PLAN_MODEL` if set,
    otherwise `pick_model(assess_difficulty(...))` - cheap for a one-line question, strong for a genuinely
    multi-part ticket. Pass `model=` to force one. If a `meter` is given, the call's cost and latency are
    recorded on it under the label `plan`, so the plan shows up in the run's cost report like any other call.
    """
    chosen = model or PLAN_MODEL or pick_model(assess_difficulty(ticket_text))
    with measure() as sw:
        response = _client().messages.create(
            model=chosen,
            max_tokens=128,
            system=PLANNER_SYSTEM,
            messages=[{"role": "user", "content": ticket_text}],
            tools=[MAKE_PLAN_TOOL],
            tool_choice={"type": "tool", "name": "make_plan"},
        )
    if meter is not None:
        meter.record("plan", chosen, response.usage, sw.ms)
    return _parse_plan(response)


def planner_node(
    state: TeamState,
    make_plan: Optional[Callable[[str], List[str]]] = None,
    meter: Optional[Meter] = None,
) -> dict:
    """Graph node: turn the ticket into a `plan` and hand it to the supervisor.

    `make_plan` is injected (defaults to the model-backed `plan_ticket`), so a test drives the whole team
    with a one-line stub - `lambda text: ["research", "refund"]` - and never touches the model. When the
    default is used and a `meter` is passed, it is threaded into `plan_ticket` so the planning call is
    metered. Writes `plan` (last-write-wins) and appends one `transcript` step naming the plan it chose.
    """
    if make_plan is None:
        plan = plan_ticket(state["ticket_text"], meter=meter)
    else:
        plan = make_plan(state["ticket_text"])
    return {"plan": plan, "transcript": [f"planner->{'+'.join(plan)}"]}


def build_planning_team(
    get_customer: Callable[[str], dict] = look_up_customer,
    make_plan: Optional[Callable[[str], List[str]]] = None,
    meter: Optional[Meter] = None,
    get_order_status: Callable[[str], dict] = _default_order_lookup,
    kb: Optional[KnowledgeBase] = None,
):
    """The supervisor team with a real planner in front of it - today's whole graph.

        START -> look_up_customer -> planner -> supervisor <-> (refund | order | research) -> END

    Structurally this is Day 1's `build_supervisor` with one node inserted: `planner` runs after the
    customer lookup and writes the `plan` the supervisor then executes, instead of the caller seeding
    `plan` by hand. The worker subgraphs and `supervisor_node` are reused unchanged from `orchestrator`
    - the multi-agent shape did not move, it just grew a brain. Every collaborator (`get_customer`,
    `make_plan`, `get_order_status`, `kb`) is injected, so the whole team runs offline in a test.
    """
    workers = build_workers(get_order_status=get_order_status, kb=kb)
    b = StateGraph(TeamState)
    b.add_node("look_up_customer", partial(look_up_customer_node, get_customer=get_customer))
    b.add_node("planner", partial(planner_node, make_plan=make_plan, meter=meter))
    b.add_node("supervisor", supervisor_node)
    for name in SPECIALTIES:
        b.add_node(name, workers[name])
        b.add_edge(name, "supervisor")
    b.add_edge(START, "look_up_customer")
    b.add_edge("look_up_customer", "planner")
    b.add_edge("planner", "supervisor")
    return b.compile()
