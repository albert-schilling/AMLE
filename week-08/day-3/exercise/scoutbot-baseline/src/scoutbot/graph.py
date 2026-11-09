"""ScoutBot's LangGraph graph, now able to choose its own path and to survive the process dying.

Day 1 made a run's facts explicit: `TicketState` declares them, and each node returns only the
fields it changed. That graph had two limits, both named out loud at the time and both closed here.

1. It always ran every node in the same order. Nothing in the graph could act on what triage
   decided, so a ticket that obviously needed a person was handled identically to one that did
   not. `route_after_triage` plus `add_conditional_edges` fixes that: the next node is chosen by
   reading state.
2. It lost everything when the process ended. `build_ticket_graph()` now takes an optional
   checkpointer, and that single argument is the whole difference between a run that vanishes and
   a run that can be picked up by a different process on Saturday morning.

The two belong together. A branch is what gives a run somewhere to stop; a checkpoint is what
makes stopping survivable. Week 7's `loop.py` still sits alongside this module untouched, and its
escalation was a *model-chosen tool call*, which is worth contrasting: the branch below is a line
of code a reviewer can read, and it decides the same thing the same way every time.

Still not here: `interrupt()`, which is what actually pauses a run for a human (Wednesday), and
any handling of the fact that a resumed node re-runs from its start (Thursday). LangGraph is used
as the orchestration layer only, and every model call still goes through the same Anthropic SDK as
Week 7 (`core.triage`).
"""
import json
import operator
import sqlite3
from pathlib import Path
from typing import Annotated, Optional, TypedDict, Union

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .core import triage
from .schema import Priority
from .tools import look_up_customer


class TicketState(TypedDict):
    """Everything one ticket run accumulates, declared once, in one place.

    Two kinds of field, on purpose:

    - Plain fields (`customer`, `triage`, `resolution`, and the three inputs) are last-write-wins.
      Whatever a node returns for one of them replaces what was there before.
    - `notes` carries a **reducer**, `operator.add`. Each node's list is appended to what is
      already in state instead of replacing it. Without that annotation, the second node's note
      would silently erase the first node's, which is the single easiest mistake to make when
      writing a state schema for the first time.

    `resolution` is new today. Only one of the two terminal nodes ever writes it, so its value
    also records which way the branch went - useful in a test, and useful on screen.
    """

    ticket_id: str
    ticket_text: str
    customer_id: str
    customer: dict
    triage: dict
    resolution: dict
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

    This is also the only node in the graph that costs money, which is what makes it the one to
    watch when a resumed run is meant not to repeat work.
    """
    result = triage(_ticket_with_customer(state))
    return {
        "triage": result.model_dump(mode="json"),
        "notes": [f"triaged as {result.category.value}/{result.priority.value}"],
    }


def route_after_triage(state: TicketState) -> str:
    """Decide which node runs next, by reading state. Returns a node name, nothing more.

    A router is an ordinary function of the state, so it can be called and tested directly with
    a hand-made dict and no graph, no model and no API key. Both branches of the day's central
    decision are therefore testable offline, which is worth pointing out to students who assume
    anything involving an LLM needs a live call to verify.

    The condition reads the *triage result* rather than asking the model what to do next. That
    distinction is the point of the topic: Week 7's escalation happened because the model chose
    to call `escalate_to_human`, so it could vary run to run. This is policy, written down once,
    reviewable by someone who does not know how the model works.
    """
    if state["triage"]["priority"] == Priority.high.value:
        return "escalate"
    return "auto_resolve"


def escalate_node(state: TicketState) -> dict:
    """Terminal node for tickets a person needs to look at.

    Deliberately does *not* call `tools.escalate_to_human`. That function blocks on a `confirm()`
    prompt, and a blocking prompt in the middle of a graph is precisely the problem Priya's Day 3
    memo complained about. Today the node records that the ticket is waiting for a human and
    ends; Wednesday's `interrupt()` is what turns "waiting" into something a run can actually do
    without holding a process open.
    """
    return {
        "resolution": {
            "path": "escalated",
            "awaiting_human": True,
            "owner": state["triage"].get("suggested_owner", "support-team"),
        },
        "notes": ["escalated: high priority, needs a human"],
    }


def auto_resolve_node(state: TicketState) -> dict:
    """Terminal node for everything else: ScoutBot handles it and the run is done."""
    return {
        "resolution": {
            "path": "auto_resolved",
            "awaiting_human": False,
            "owner": state["triage"].get("suggested_owner", "support-team"),
        },
        "notes": ["auto-resolved: no human needed"],
    }


def build_ticket_graph(checkpointer: Optional[BaseCheckpointSaver] = None):
    """Wire the graph up and compile it.

        START -> look_up_customer -> triage_ticket -> (escalate | auto_resolve) -> END

    Two things to notice about `add_conditional_edges`. The router returns a *label*, and the path
    map says which node each label means, so the graph's shape stays readable without reading the
    router. And the labels happen to match the node names here, which is convenient but not
    required; keeping the map explicit is what lets the branch be renamed later without touching
    the router.

    `checkpointer` is the day's other half, and the reason this signature grew by exactly one
    optional argument. Left as `None`, this compiles to Day 1's throwaway graph: it runs, then
    forgets. Given a saver, LangGraph writes the state to it after every completed node, and any
    later call with the same `thread_id` picks the run up from where it stopped. Nothing else in
    this function changes, which is the part worth saying out loud.
    """
    builder = StateGraph(TicketState)
    builder.add_node("look_up_customer", look_up_customer_node)
    builder.add_node("triage_ticket", triage_ticket_node)
    builder.add_node("escalate", escalate_node)
    builder.add_node("auto_resolve", auto_resolve_node)
    builder.add_edge(START, "look_up_customer")
    builder.add_edge("look_up_customer", "triage_ticket")
    builder.add_conditional_edges(
        "triage_ticket",
        route_after_triage,
        {"escalate": "escalate", "auto_resolve": "auto_resolve"},
    )
    builder.add_edge("escalate", END)
    builder.add_edge("auto_resolve", END)
    return builder.compile(checkpointer=checkpointer)


def sqlite_checkpointer(db_path: Union[str, Path]) -> SqliteSaver:
    """A checkpointer that writes to a file, so a run outlives the process that started it.

    `InMemorySaver` is enough to see checkpointing work, and it is the right first thing to try,
    but it lives in the same process it is supposed to protect against losing. Only a file-backed
    saver answers the Saturday-morning question.

    `check_same_thread=False` is needed because LangGraph may touch the connection from a worker
    thread, which is not the thread that opened it. `SqliteSaver` takes a plain
    `sqlite3.Connection`, so it can be built here and used for as long as the process lives;
    `SqliteSaver.from_conn_string()` exists too, but it is a context manager, and a graph
    compiled inside a `with` block stops working once the block exits.
    """
    return SqliteSaver(sqlite3.connect(str(db_path), check_same_thread=False))


def thread_config(thread_id: str) -> dict:
    """The config that tells a checkpointed graph *which* run this is.

    `thread_id` is the key everything is stored under, so it is worth choosing deliberately: the
    ticket ID is a good choice here, since one ticket is one run. Two different IDs are two
    independent runs sharing one database and never seeing each other's state. Reusing an ID by
    accident is how a run gets resumed into the wrong ticket's history.
    """
    return {"configurable": {"thread_id": thread_id}}


def initial_state(
    ticket_text: str, customer_id: str, ticket_id: Optional[str] = None
) -> TicketState:
    """The starting state for one run.

    `customer`, `triage`, `resolution` and `notes` start empty rather than absent, so a printed
    run shows every declared field from the first line, including the accumulating one before
    anything has accumulated into it.
    """
    return {
        "ticket_id": ticket_id or "",
        "ticket_text": ticket_text,
        "customer_id": customer_id,
        "customer": {},
        "triage": {},
        "resolution": {},
        "notes": [],
    }


def run_ticket_graph(
    ticket_text: str, customer_id: str, ticket_id: Optional[str] = None
) -> TicketState:
    """Run one ticket all the way through the graph and return the final state.

    No checkpointer, so this is the throwaway version: fine for a one-shot run, and unchanged
    from Day 1 on purpose.
    """
    graph = build_ticket_graph()
    return graph.invoke(initial_state(ticket_text, customer_id, ticket_id))
