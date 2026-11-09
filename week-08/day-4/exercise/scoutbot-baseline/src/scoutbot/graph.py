"""ScoutBot's LangGraph graph: it chooses its path, survives the process dying, and now waits.

Day 1 made a run's facts explicit. Day 2 let the graph choose its next node by reading state, and
gave it a checkpointer so a run could be picked up by a different process. Both of those left one
thing conspicuously unfinished, and today finishes it.

Day 2's `escalate` node wrote `awaiting_human: True` into state and then ended the run. That is a
*note about* a human, not a pause for one. `interrupt()` is the real thing: the node stops, the run
ends, the process can exit, and the question is recorded in the checkpoint. Whenever an answer
arrives, `Command(resume=value)` continues that thread, and `value` comes back as the return value
of the `interrupt()` call the node stopped at.

The other half of today is why that pause is visible at all. A run is a stream of **events**, not
a function that returns once. `draft_reply` proves it: the reply is emitted piece by piece through
LangGraph's stream writer while the node is still working, so a reviewer reads it as it forms
rather than waiting for the node to finish. The pause arrives on the same stream, as an
`__interrupt__` event.

Two facts worth having in front of you before editing this file, both from a spike against
langgraph 1.2.10 rather than from the docs:

- **A checkpointer is not optional any more.** `interrupt()` needs somewhere to record the pause.
  Without one, nothing raises: `invoke()` returns the state with an `__interrupt__` key, the
  pausing node's return value never materialises, and the failure only shows up later, when
  resuming raises `RuntimeError: Cannot use Command(resume=...) without checkpointer`. That is why
  `build_ticket_graph()` now defaults to an `InMemorySaver` rather than to no checkpointer at all.
  `ticket_graph_builder()` is exposed so a test can still compile the un-checkpointed version and
  demonstrate the trap.
- **A resumed node restarts from its first line.** Everything above the `interrupt()` call runs a
  second time; nodes that already finished do not run again. That asymmetry is Thursday's
  idempotency topic, and it is the reason `draft_reply` is its own node rather than the first half
  of `escalate`: the model call sits *above* no pause, so resuming never pays for it twice.

LangGraph is the orchestration layer only. Every model call still goes through the same Anthropic
SDK as Week 7 (`core.triage`, and now `core.stream_reply`), which is also why tokens reach the
stream through `stream_mode="custom"` and the writer: with no LangChain chat model in the stack,
there is nothing for `stream_mode="messages"` to hook into. Week 7's `loop.py` sits alongside this
module, still untouched.
"""
import json
import operator
import sqlite3
from pathlib import Path
from typing import Annotated, Optional, TypedDict, Union

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import StreamWriter, interrupt

from .core import stream_reply, triage
from .schema import Priority
from .tools import look_up_customer


def _no_writer(_event) -> None:
    """The default writer for a node called outside a graph: accept the event, drop it.

    Exists so `draft_reply_node` stays an ordinary function. See its docstring for why that is
    worth a module-level default.
    """


class TicketState(TypedDict):
    """Everything one ticket run accumulates, declared once, in one place.

    Two kinds of field, on purpose:

    - Plain fields (`customer`, `triage`, `resolution`, and the three inputs) are last-write-wins.
      Whatever a node returns for one of them replaces what was there before.
    - `notes` carries a **reducer**, `operator.add`. Each node's list is appended to what is
      already in state instead of replacing it. Without that annotation, the second node's note
      would silently erase the first node's, which is the single easiest mistake to make when
      writing a state schema for the first time.

    `resolution` records which way the branch went, since only one of the two terminal nodes ever
    writes it - useful in a test, and useful on screen.

    `draft_reply` is new today, and it is the field that makes the streaming visible in two ways at
    once. Its *pieces* go out as events while `draft_reply_node` is still running, and its finished
    text lands here, in state, where the pause can put it in front of a human.
    """

    ticket_id: str
    ticket_text: str
    customer_id: str
    customer: dict
    triage: dict
    draft_reply: str
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


def draft_reply_node(state: TicketState, writer: StreamWriter = _no_writer) -> dict:
    """Third node: draft the reply, emitting it as it is written.

    A `writer` is a function that puts anything JSON-serialisable onto the run's stream, and a
    caller streaming with `stream_mode="custom"` receives each item the moment it is written. So
    the reply reaches a screen while this node is still working, seconds before the node has
    returned anything at all. That is the whole streaming half of the day.

    **There are two ways to get hold of that writer, and the choice here is deliberate.** The docs
    reach for `get_stream_writer()`, called inside the node body. That works, including in a plain
    synchronous node on Python 3.10 (the docs' caveat about it being unavailable applies to *async*
    nodes before 3.11), but it has a cost worth refusing: it reads a context variable that only
    exists while LangGraph is driving, so a node written that way raises `RuntimeError: Called
    get_config outside of a runnable context` when you call it as an ordinary function. Day 1's
    best property, that a node can be called and tested with a hand-made dict and no graph
    anywhere, would quietly stop being true.

    Declaring `writer` as a parameter instead gets it injected by name, which LangGraph does for any
    node with a parameter named `writer` annotated `StreamWriter`. Inside a graph it is the real
    writer. Outside one, the default below keeps this a function you can just call, and a test can
    pass its own collector and assert on exactly what was emitted. Same mechanism either way, minus
    the trap.

    When nobody is streaming custom events at all, under `invoke()` or a `stream()` without
    `"custom"` in its modes, the injected writer is a no-op, so this node needs no guard.

    Drafting happens before the branch, so both outcomes have a reply: one for a human to approve,
    one for ScoutBot to send. Keeping it in its own node is also what stops the model being paid
    for twice when a paused run resumes, since a resumed node re-runs everything above its
    `interrupt()` call and there is no pause in this one.
    """
    context = (
        f"Triaged as {state['triage'].get('category')} / "
        f"{state['triage'].get('priority')} priority."
    )
    text = stream_reply(
        state["ticket_text"],
        on_chunk=lambda chunk: writer({"draft_chunk": chunk}),
        context=context,
    )
    return {"draft_reply": text, "notes": ["drafted a reply"]}


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
    """Terminal node for tickets a person needs to look at. This one actually waits.

    `interrupt()` is the whole of it. Execution stops on that line, the run ends, and the payload
    handed to it is what the caller sees: everything a reviewer needs in order to decide, which is
    why the drafted reply is in there rather than just a ticket ID. The process is free to exit. The
    question is in the checkpoint, filed under this run's `thread_id`.

    When someone answers, `Command(resume=value)` continues the thread and `value` is returned by
    the `interrupt()` call below. Note what LangGraph does *not* do: it never validates that value.
    Whatever the caller passes arrives here as-is, so this node accepts either the dict it expects
    or a bare boolean, because `Command(resume=True)` is the form every tutorial uses and a
    `KeyError` from someone else's example is a poor lesson.

    Still deliberately not calling `tools.escalate_to_human`. Its blocking `confirm()` prompt is
    exactly what a pause replaces: this run does not hold a process open while it waits.

    Note also what re-runs. Everything above the `interrupt()` line executes again on resume, which
    is harmless here because there is nothing above it. Putting a model call or a database write
    there would not be harmless, and that is Thursday's topic.
    """
    decision = interrupt(
        {
            "question": "Send this reply, or handle it yourself?",
            "ticket_id": state["ticket_id"],
            "why": (
                f"{state['triage'].get('category')} at "
                f"{state['triage'].get('priority')} priority"
            ),
            # What a reviewer would actually want to know about this account, rather than an ID
            # they would have to look up themselves.
            "account": (
                f"{state['customer_id']} on the {state['customer'].get('plan', 'unknown')} plan, "
                f"{state['customer'].get('past_refunds_90d', '?')} refunds in 90 days"
            ),
            "draft_reply": state["draft_reply"],
        }
    )
    approved = decision["approved"] if isinstance(decision, dict) else bool(decision)
    reviewer = decision.get("by", "unknown") if isinstance(decision, dict) else "unknown"
    return {
        "resolution": {
            "path": "escalated",
            "awaiting_human": False,
            "approved": approved,
            "reviewed_by": reviewer,
            "owner": state["triage"].get("suggested_owner", "support-team"),
        },
        "notes": [f"human {'approved' if approved else 'rejected'} the draft: {reviewer}"],
    }


def auto_resolve_node(state: TicketState) -> dict:
    """Terminal node for everything else: ScoutBot sends the draft itself and the run is done.

    No pause, so no checkpointer strictly required for this branch, and nothing here re-runs. The
    contrast with `escalate_node` is the point: same graph, same drafted reply, and the only
    difference is whether a person is asked.
    """
    return {
        "resolution": {
            "path": "auto_resolved",
            "awaiting_human": False,
            "approved": True,
            "reviewed_by": "scoutbot",
            "owner": state["triage"].get("suggested_owner", "support-team"),
        },
        "notes": ["auto-resolved: sent the drafted reply, no human needed"],
    }


def ticket_graph_builder() -> StateGraph:
    """The graph's shape, un-compiled.

        START -> look_up_customer -> triage_ticket -> draft_reply
              -> (escalate | auto_resolve) -> END

    Two things to notice about `add_conditional_edges`. The router returns a *label*, and the path
    map says which node each label means, so the graph's shape stays readable without reading the
    router. And the labels happen to match the node names here, which is convenient but not
    required; keeping the map explicit is what lets the branch be renamed later without touching
    the router.

    Exposed separately from `build_ticket_graph()` for one reason: a test needs to compile this
    without any checkpointer in order to show what an un-checkpointed `interrupt()` actually does
    (see `tests/test_graph.py`). Normal code should call `build_ticket_graph()`.
    """
    builder = StateGraph(TicketState)
    builder.add_node("look_up_customer", look_up_customer_node)
    builder.add_node("triage_ticket", triage_ticket_node)
    builder.add_node("draft_reply", draft_reply_node)
    builder.add_node("escalate", escalate_node)
    builder.add_node("auto_resolve", auto_resolve_node)
    builder.add_edge(START, "look_up_customer")
    builder.add_edge("look_up_customer", "triage_ticket")
    builder.add_edge("triage_ticket", "draft_reply")
    builder.add_conditional_edges(
        "draft_reply",
        route_after_triage,
        {"escalate": "escalate", "auto_resolve": "auto_resolve"},
    )
    builder.add_edge("escalate", END)
    builder.add_edge("auto_resolve", END)
    return builder


def build_ticket_graph(checkpointer: Optional[BaseCheckpointSaver] = None):
    """Compile the graph, with a checkpointer it can no longer do without.

    `None` no longer means "no checkpointer". As of today the graph contains an `interrupt()`, and
    a pause has to be recorded somewhere or it cannot be resumed, so `None` means an
    `InMemorySaver`: memory that lasts as long as this process. Pass `sqlite_checkpointer(...)`
    when the run needs to outlive it, exactly as on Day 2.

    That change is worth one sentence out loud when teaching, because it reframes yesterday.
    Tuesday the checkpointer was the argument that bought durability. Today it is the precondition
    for being able to stop at all.

    Any call that reaches `escalate` now also needs a `thread_id` in its config, since that is what
    names the paused run. `thread_config()` below builds one.
    """
    return ticket_graph_builder().compile(checkpointer=checkpointer or InMemorySaver())


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

    `customer`, `triage`, `draft_reply`, `resolution` and `notes` start empty rather than absent,
    so a printed run shows every declared field from the first line, including the accumulating one
    before anything has accumulated into it.
    """
    return {
        "ticket_id": ticket_id or "",
        "ticket_text": ticket_text,
        "customer_id": customer_id,
        "customer": {},
        "triage": {},
        "draft_reply": "",
        "resolution": {},
        "notes": [],
    }


def run_ticket_graph(
    ticket_text: str, customer_id: str, ticket_id: Optional[str] = None
) -> TicketState:
    """Run one ticket until the graph either finishes or stops to ask a human.

    "Until" is doing real work in that sentence, and it is new today. A low-priority ticket runs
    to `END` and this returns the finished state, as it has since Day 1. A high-priority one stops
    inside `escalate`, and what comes back is the state *plus* an `__interrupt__` key holding the
    question. Nothing raises, and `resolution` is simply still empty, so a caller that assumes a
    finished run will quietly get a half-finished one.

    That is not a wart to be smoothed over, it is what pausing looks like from the outside, and
    `run_events.py` exists to show it properly. This helper takes a `thread_id` from the ticket ID
    because a paused run has to be filed under a name to be resumable at all.
    """
    graph = build_ticket_graph()
    return graph.invoke(
        initial_state(ticket_text, customer_id, ticket_id),
        thread_config(ticket_id or "unnamed-run"),
    )
