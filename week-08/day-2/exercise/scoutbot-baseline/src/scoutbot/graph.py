"""ScoutBot's first LangGraph graph: the same look-up-then-triage sequence Week 7's loop
already performs, rebuilt so a run's facts live in one declared place instead of in local
variables.

Week 7's `loop.py` keeps everything it knows in Python locals - the `messages` list, `steps`,
each observation as it arrives. That works exactly as long as the process keeps running. The
moment it stops, every fact about that run is gone, which is the specific problem Priya's Day 3
memo argued LangGraph would fix (see week-07/day-3/solution/example-memo.md).

This module is only the first half of fixing it: making state **explicit**. `TicketState`
declares what one ticket run accumulates, and each node returns just the fields it changed.
Nothing here is durable yet - durability needs a checkpointer, which is tomorrow's topic. State
being explicit is the precondition for that, not the payoff itself.

Deliberately smaller than `loop.py`, and that is the point of the day: two fixed nodes joined by
one straight path, with no model-chosen tool sequence, no escalation branch and no step cap.
Week 7's loop stays here untouched as the "before". Tomorrow's conditional edge is where the
escalation path comes back, exactly as Priya predicted in that memo's last section.

LangGraph is used as the orchestration layer only. The state's accumulating field is a plain
`Annotated[list[str], operator.add]`, and every model call still goes through the same Anthropic
SDK as Week 7 (`core.triage`), so there is no `langchain-anthropic` dependency and no LangChain
chat-model abstraction anywhere in this repo.
"""
import json
import operator
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from .core import triage
from .tools import look_up_customer


class TicketState(TypedDict):
    """Everything one ticket run accumulates, declared once, in one place.

    Two kinds of field, on purpose:

    - Plain fields (`customer`, `triage`, and the three inputs) are last-write-wins. Whatever a
      node returns for one of them replaces what was there before.
    - `notes` carries a **reducer**, `operator.add`. Each node's list is appended to what is
      already in state instead of replacing it. Without that annotation, the second node's note
      would silently erase the first node's, which is the single easiest mistake to make when
      writing a state schema for the first time.
    """

    ticket_id: str
    ticket_text: str
    customer_id: str
    customer: dict
    triage: dict
    notes: Annotated[list[str], operator.add]


def _ticket_with_customer(state: TicketState) -> str:
    """Fold the looked-up record into the text `triage()` sees.

    `triage()` keeps its Week 7 Day 1 signature (one string in, a validated `TicketTriage`
    out), so the node hands the customer record over as part of the ticket rather than as a new
    argument. Week 7's code stays untouched; only where its input comes from is new.
    """
    return (
        f"{state['ticket_text']}\n\n"
        f"Customer record: {json.dumps(state['customer'], sort_keys=True)}"
    )


def look_up_customer_node(state: TicketState) -> dict:
    """First node: read the customer record, write it into state.

    Returns only the two fields it changed, not a whole new state dict. LangGraph merges a
    node's return value into the existing state, applying each field's reducer as it goes.
    Returning everything would also work, but then it stops being obvious which node is
    responsible for which fact.
    """
    record = look_up_customer(state["customer_id"])
    outcome = "found" if record.get("found") else "not found"
    return {
        "customer": record,
        "notes": [f"looked up {state['customer_id']}: {outcome}"],
    }


def triage_ticket_node(state: TicketState) -> dict:
    """Second node: triage the ticket using what the first node wrote.

    This is the whole reason shared state matters. The decision is not made from the ticket
    text alone; it is made from the ticket text plus the customer record already sitting in
    state. Nothing is passed between the two functions directly - they only ever meet through
    `TicketState`.
    """
    result = triage(_ticket_with_customer(state))
    return {
        "triage": result.model_dump(mode="json"),
        "notes": [f"triaged as {result.category.value}/{result.priority.value}"],
    }


def build_ticket_graph():
    """Wire the two nodes up and compile: START to look_up_customer to triage_ticket to END.

    `compile()` is also where a checkpointer gets passed, which is how tomorrow's session makes
    this same graph durable. The wiring below does not change to get there, only what is handed
    to `compile()` does.

    The compiled graph is reusable across tickets, so callers running a batch should build it
    once (see `run_graph.py`) rather than per ticket.
    """
    builder = StateGraph(TicketState)
    builder.add_node("look_up_customer", look_up_customer_node)
    builder.add_node("triage_ticket", triage_ticket_node)
    builder.add_edge(START, "look_up_customer")
    builder.add_edge("look_up_customer", "triage_ticket")
    builder.add_edge("triage_ticket", END)
    return builder.compile()


def initial_state(
    ticket_text: str, customer_id: str, ticket_id: Optional[str] = None
) -> TicketState:
    """The starting state for one run.

    `customer`, `triage` and `notes` start empty rather than absent, so a printed run shows
    every declared field from the first line, including the accumulating one before anything
    has accumulated into it.
    """
    return {
        "ticket_id": ticket_id or "",
        "ticket_text": ticket_text,
        "customer_id": customer_id,
        "customer": {},
        "triage": {},
        "notes": [],
    }


def run_ticket_graph(
    ticket_text: str, customer_id: str, ticket_id: Optional[str] = None
) -> TicketState:
    """Run one ticket all the way through the graph and return the final state."""
    graph = build_ticket_graph()
    return graph.invoke(initial_state(ticket_text, customer_id, ticket_id))
