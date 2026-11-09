"""ScoutBot's LangGraph graph: it chooses its path, survives a restart, waits, and now acts once.

Day 1 made a run's facts explicit. Day 2 let the graph choose its next node by reading state and
gave it a checkpointer, so a run could be picked up by a different process. Day 3 made the run stop
and ask a person, and made its progress visible as events. Two things were still missing, and today
is both of them.

**Who gets asked, and why.** Until today "needs a human" was one line reading `priority == "high"`,
so every escalation looked the same and the payload asked an anonymous nobody. Now `check_policy`
runs [policy.decide_approval][] over the run's facts and writes the answer into state: whether a
human is needed, which approver is required, and the rule that decided it. The router shrinks to a
state lookup, which is what Tuesday said a router should be. And `escalate` names the required
approver in its payload and **checks the answer it gets back**, because Wednesday established that
LangGraph never validates a resume value.

**Acting once.** `send_reply` is new and is the only node in this repo that does something to the
outside world. That makes it the node where the week's quietest fact finally bites: a node's code
can run more than once for one logical run. A resumed node re-runs from its first line, which Day 3
proved with a counter, and a **retried** node does the same, which is one argument to `add_node()`
away. The first can be designed around by putting the side effect below the pause, which is exactly
why `send_reply` is its own node. The second cannot be designed around at all, so the guarantee
comes from [notify.send_reply][] and its ledger instead.

Four facts worth having in front of you before editing this file, all from a local spike against
langgraph 1.2.10 rather than from the docs:

- **A checkpointer is not optional.** `interrupt()` needs somewhere to record the pause. Without
  one, nothing raises: `invoke()` returns the state with an `__interrupt__` key, the pausing node's
  return value never materialises, and the failure only shows up later, when resuming raises
  `RuntimeError: Cannot use Command(resume=...) without checkpointer`. Hence `build_ticket_graph()`
  defaulting to an `InMemorySaver`; `ticket_graph_builder()` stays exposed so a test can compile the
  un-checkpointed version and demonstrate the trap.
- **A resumed node restarts from its first line**, and a retried one does too. Nodes that already
  finished do not run again either way.
- **`retry_policy` does not retry a pause.** A node that calls `interrupt()` while carrying a
  `RetryPolicy` pauses cleanly rather than treating the interrupt as a retryable failure. Verified,
  because `interrupt()` raises internally and the default `retry_on` is otherwise generous, so the
  safe behaviour is not obvious from reading the types.
- **`cache_policy` is not the answer to any of this**, and is silently inert unless `compile()` is
  also given a `cache=`. It caches a node's return value keyed by its input hash, which knows
  nothing about whether an email left the building.

LangGraph is the orchestration layer only. Every model call still goes through the same Anthropic
SDK as Week 7 (`core.triage`, `core.stream_reply`), which is also why tokens reach the stream
through `stream_mode="custom"` and the writer: with no LangChain chat model in the stack, there is
nothing for `stream_mode="messages"` to hook into. Week 7's `loop.py` sits alongside this module,
still untouched.
"""
import json
import operator
import sqlite3
from functools import partial
from pathlib import Path
from typing import Annotated, Optional, TypedDict, Union

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, StreamWriter, interrupt
from opentelemetry.trace import Tracer

from .core import stream_reply, triage
from .notify import Ledger, send_reply
from .policy import approval_for_state, is_authorised
from .tracing import trace_node
from .tools import look_up_customer

SEND_RETRY_POLICY = RetryPolicy(max_attempts=3, initial_interval=0.1, backoff_factor=2.0)
"""Retries for the one node that talks to something outside this process.

Three attempts, and the first one 100ms later. The numbers matter less than which node carries the
policy: a transient network failure is worth retrying, and a bug in our own code is not, which is
roughly what LangGraph's default `retry_on` already encodes (it retries `ConnectionError` and 5xx
responses, and deliberately does not retry `ValueError`, `TypeError` or `KeyError`).

The reason this is a named constant rather than an inline argument is that it is the thing which
makes idempotency non-optional. Put a retry policy on a node with a side effect and you have just
declared that the side effect may happen several times, unless something stops it.
"""


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

    `draft_reply` carries the streamed reply: its *pieces* go out as events while
    `draft_reply_node` is still running, and its finished text lands here, where the pause can put it
    in front of a human.

    Two fields are new today, and the difference between them is worth noticing.
    `refund_amount` is an **input**, looked up from billing and handed in with the ticket, which is
    why it sits next to `ticket_text` rather than being written by a node. `approval` is a
    **decision**, written by `check_policy` from facts already in state, so the run keeps a record of
    what the policy said and why, and the router has something to read.

    What is deliberately *not* here: any field recording that the reply was sent. That was the
    obvious place to put it and it does not work, which is most of today's second topic. See
    [notify][] for what happens instead, and why.
    """

    ticket_id: str
    ticket_text: str
    customer_id: str
    refund_amount: float
    customer: dict
    triage: dict
    draft_reply: str
    approval: dict
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


def check_policy_node(state: TicketState) -> dict:
    """Fourth node: apply the approval policy and write down what it decided.

    Two lines of code, and it replaces the entire routing condition from Day 2. The work is all in
    [policy.decide_approval][], which is a pure function over four plain values; this node only
    unpacks state and records the answer.

    Recording it, rather than deciding inside the router, is the deliberate part. Three things fall
    out of having `approval` in state:

    - the run keeps a permanent record of which rule fired, so a decision can be explained a week
      later without re-deriving it from a customer record that may have changed since
    - `escalate` and `send_reply` both read the same decision instead of each recomputing it, so
      they cannot disagree
    - the router shrinks to a state lookup, which is what Tuesday said a router is for

    It costs one extra node in the graph and it makes the policy a visible step in the run rather
    than an invisible condition on an edge. For anything a human might later have to justify, that
    trade is worth making.
    """
    approval = approval_for_state(state)
    return {
        "approval": {
            "needs_human": approval.needs_human,
            "approver": approval.approver,
            "reason": approval.reason,
        },
        "notes": [
            f"policy: {'needs ' + approval.approver if approval.needs_human else 'no human needed'}"
            f" ({approval.reason})"
        ],
    }


def route_on_approval(state: TicketState) -> str:
    """Decide which node runs next by reading the decision `check_policy` already made.

    Replaces Day 2's `route_after_triage`, which read the triage priority directly. The change is
    worth naming when teaching: the router did not get smarter, it got *dumber*, and that is the
    improvement. The judgement moved into a pure function that can be unit-tested exhaustively and
    read by the person who owns the policy, leaving the router to do one thing.

    Still an ordinary function of the state, so both branches are testable with a hand-made dict and
    no graph, no model and no API key.
    """
    return "escalate" if state["approval"].get("needs_human") else "auto_approve"


def escalate_node(state: TicketState) -> dict:
    """The node that waits for the named approver, and checks who answered.

    `interrupt()` is still the whole of the pause. Execution stops on that line, the run ends, the
    process is free to exit, and the question is in the checkpoint under this run's `thread_id`.
    When someone answers, `Command(resume=value)` continues the thread and `value` is returned by
    the `interrupt()` call below.

    What is new today is on both sides of that call.

    **Going out:** the payload names the approver the policy requires, and the rule that required
    them. "A human needs to look at this" is not an actionable request; "a billing manager needs to
    look at this, because the account has had four refunds in ninety days" is. The person reading it
    can tell immediately whether it is theirs to answer.

    **Coming back:** the answer is checked against the policy with [policy.is_authorised][]. This is
    not defensive programming for its own sake, it is the direct consequence of Wednesday's finding
    that LangGraph never validates a resume value. Whatever the caller passes arrives here as-is, so
    a support lead claiming to approve a billing-manager decision arrives looking exactly like a
    billing manager approving one. Only this node can tell the difference, so it has to.

    The resume value therefore carries three things: `approved`, `by` (which person) and `role`
    (what they are). Only the last of those is checked, because a policy has opinions about roles
    and not about people, but `by` is what makes the decision auditable afterwards.

    An unauthorised approval is deliberately **not** an exception. It is recorded as a
    non-approval, with a reason, and the run continues to `send_reply`, which then sends nothing.
    That keeps the failure inspectable in the run's own record instead of as a traceback, and it
    means an under-powered approval cannot be mistaken for a rejection by whoever reads the state
    later. The alternative worth mentioning to a student who asks is a second `interrupt()` in this
    node, asking again until somebody authorised answers, which does work (an already-answered
    `interrupt()` replays its stored value rather than pausing again) at the cost of a node that can
    pause an unbounded number of times.

    Still deliberately not calling `tools.escalate_to_human`. Its blocking `confirm()` prompt is
    exactly what a pause replaces: this run does not hold a process open while it waits.

    Nothing above the `interrupt()` call does anything irreversible, which is why resuming this node
    is free. That is not luck, it is the reason the sending lives in its own node downstream.
    """
    required = state["approval"].get("approver", "unknown")
    decision = interrupt(
        {
            "question": f"Approve this reply? Requires: {required}",
            "ticket_id": state["ticket_id"],
            "approver_required": required,
            "why": state["approval"].get("reason", ""),
            "amount": state.get("refund_amount", 0.0),
            # What a reviewer would actually want to know about this account, rather than an ID
            # they would have to look up themselves.
            "account": (
                f"{state['customer_id']} on the {state['customer'].get('plan', 'unknown')} plan, "
                f"{state['customer'].get('past_refunds_90d', '?')} refunds in 90 days"
            ),
            "draft_reply": state["draft_reply"],
        }
    )

    # `Command(resume=True)` is the form every tutorial uses, so a bare boolean is accepted rather
    # than punished with a KeyError from somebody else's example. It carries no role, though, so it
    # cannot satisfy an authorisation check - which is itself worth showing rather than smoothing
    # over, because it is what "LangGraph does not validate the resume value" costs you.
    if isinstance(decision, dict):
        claimed = bool(decision.get("approved"))
        reviewer = decision.get("by", "unknown")
        role = decision.get("role")
    else:
        claimed, reviewer, role = bool(decision), "unknown", None

    # Two separate facts, deliberately. `by` is *who* answered, which is what an audit trail needs;
    # `role` is *what they are*, which is the only part the policy has an opinion about. Conflating
    # them works right up until two people share a job title.
    authorised = is_authorised(required, role)
    approved = bool(claimed and authorised)

    if not authorised:
        note = f"{reviewer} ({role or 'no role given'}) may not approve this: {required} required"
    else:
        note = f"{reviewer} {'approved' if approved else 'rejected'} the draft"

    return {
        "resolution": {
            "path": "escalated",
            "awaiting_human": False,
            "approved": approved,
            "authorised": authorised,
            "approver_required": required,
            "reviewed_by": reviewer,
            "reviewer_role": role,
            "owner": state["triage"].get("suggested_owner", "support-team"),
        },
        "notes": [note],
    }


_PROCESS_LEDGER: Optional[Ledger] = None


def _process_ledger() -> Ledger:
    """One in-memory ledger per process, for callers that did not supply one.

    Deliberately not durable: it lasts exactly as long as this Python process, so it protects a
    retry (same process, seconds apart) and not a resume in a new process (which is what
    `Ledger.at(path)` is for). Same shape of choice as `InMemorySaver` versus `SqliteSaver` on
    Tuesday, and worth pointing at for exactly that reason.
    """
    global _PROCESS_LEDGER
    if _PROCESS_LEDGER is None:
        _PROCESS_LEDGER = Ledger.in_memory()
    return _PROCESS_LEDGER


def auto_approve_node(state: TicketState) -> dict:
    """The branch for tickets the policy says nobody needs to see. No pause, no person.

    Replaces Day 2's `auto_resolve`, and the rename is meaningful rather than cosmetic: this node no
    longer claims to have sent anything. All it does is record that the policy approved the reply on
    ScoutBot's behalf, and then the run goes to the same `send_reply` node the escalated branch goes
    to.

    That convergence is the point. There is exactly one place in this graph that sends a customer an
    email, so the once-only guarantee is written once and covers both paths. A version of this that
    sent from each branch would need the same guard twice, and the second copy is the one that would
    get it wrong.
    """
    return {
        "resolution": {
            "path": "auto_approved",
            "awaiting_human": False,
            "approved": True,
            "authorised": True,
            "approver_required": state["approval"].get("approver", "scoutbot"),
            "reviewed_by": "scoutbot",
            "owner": state["triage"].get("suggested_owner", "support-team"),
        },
        "notes": ["auto-approved by policy, no human needed"],
    }


def send_reply_node(
    state: TicketState,
    ledger: Optional[Ledger] = None,
    fail_after_send: int = 0,
) -> dict:
    """The last node, the only one with a side effect, and the reason today has a second topic.

    Both branches arrive here. If the reply was approved it goes to the customer; if it was
    rejected, or approved by somebody not entitled to, nothing is sent and the run says so.

    This node carries `SEND_RETRY_POLICY` in the builder below, which is the whole problem in one
    argument: a transient failure anywhere in this function makes LangGraph run the function again
    from its first line, and "again" includes the send. The protection is not here, it is in
    [notify.send_reply][], keyed on the ticket, because a guard that lived in this node would have to
    survive the node restarting, and nothing in a restarted node's local scope does.

    `ledger` is a parameter rather than a module global so that this stays a function you can call
    with a hand-made dict and your own in-memory ledger, exactly like every other node in this
    package. The builder binds the real one with `functools.partial`, which LangGraph accepts as a
    node and which leaves the signature (and therefore the injection LangGraph does by parameter
    name) intact.

    When no ledger is passed at all it falls back to one shared for the lifetime of the process, and
    that fallback is worth one sentence because getting it wrong is instructive. Creating a fresh
    `Ledger.in_memory()` per call would read as a harmless default and would quietly break the only
    thing this node exists to do: each retry would get an empty ledger, find no record, and send
    again. A guarantee about repeated calls cannot be stored anywhere that repeated calls recreate.

    `fail_after_send` is a test and demo hook, and it defaults to off. It exists so the failure can
    be put where the real one goes: after the email is gone, not before. See
    [notify.send_reply][] for why that distinction decides whether this topic teaches anything.
    """
    resolution = state.get("resolution") or {}
    if not resolution.get("approved"):
        reason = "not approved" if resolution.get("authorised", True) else "not authorised"
        return {"notes": [f"nothing sent: {reason}"]}

    outcome = send_reply(
        ticket_id=state["ticket_id"],
        text=state["draft_reply"],
        ledger=ledger if ledger is not None else _process_ledger(),
        fail_after_send=fail_after_send,
    )
    if outcome["skipped"]:
        # Worth wording carefully. This note is what a person reads afterwards, and "already sent"
        # on its own invites the reading that nothing was ever sent at all.
        return {
            "notes": [
                f"reply already sent for {state['ticket_id']}, so this attempt sent nothing"
            ]
        }
    return {"notes": [f"reply sent to the customer (ledger key {outcome['key']})"]}


def ticket_graph_builder(
    ledger: Optional[Ledger] = None,
    fail_after_send: int = 0,
    tracer: Optional[Tracer] = None,
) -> StateGraph:
    """The graph's shape, un-compiled.

        START -> look_up_customer -> triage_ticket -> draft_reply -> check_policy
              -> (escalate | auto_approve) -> send_reply -> END

    Two things changed shape on Day 4. The branch hangs off `check_policy` rather than `draft_reply`,
    and both of its arms **rejoin** at `send_reply` instead of running to `END` separately. A diamond
    rather than a fork, and the reason is the one place in the graph that does something irreversible:
    it should be one place, so the guarantee about it is written once.

    `send_reply` is also the only node with a `retry_policy`, which is the argument that turns
    "this node might run twice" from a theoretical property into a scheduled one.

    Two things to notice about `add_conditional_edges`, unchanged from Day 2. The router returns a
    *label*, and the path map says which node each label means, so the graph's shape stays readable
    without reading the router. And the labels happen to match the node names, which is convenient
    but not required.

    `ledger` and `fail_after_send` are bound into `send_reply` with `functools.partial`. LangGraph
    accepts a partial as a node action, and the node stays an ordinary function that a test can call
    directly with its own ledger.

    `tracer` is Day 5's one addition, and it is off unless asked for. When a tracer is passed, every
    node is wrapped by `trace_node` so entering it opens a span - the node's *body* is untouched, the
    wrap is signature-preserving so LangGraph still injects `writer` into `draft_reply`, and an
    un-traced build is byte-for-byte the graph Day 4 shipped. That opt-in-by-default choice is why
    Day 4's whole test suite still passes: nothing that did not ask for a span gets one.

    Exposed separately from `build_ticket_graph()` for one reason: a test needs to compile this
    without any checkpointer in order to show what an un-checkpointed `interrupt()` actually does
    (see `tests/test_graph.py`). Normal code should call `build_ticket_graph()`.
    """

    def node(name: str, action):
        """Wrap a node in a span when tracing is on, and leave it exactly as it was when off."""
        return trace_node(action, name, tracer) if tracer is not None else action

    builder = StateGraph(TicketState)
    builder.add_node("look_up_customer", node("look_up_customer", look_up_customer_node))
    builder.add_node("triage_ticket", node("triage_ticket", triage_ticket_node))
    builder.add_node("draft_reply", node("draft_reply", draft_reply_node))
    builder.add_node("check_policy", node("check_policy", check_policy_node))
    builder.add_node("escalate", node("escalate", escalate_node))
    builder.add_node("auto_approve", node("auto_approve", auto_approve_node))
    builder.add_node(
        "send_reply",
        node(
            "send_reply",
            partial(send_reply_node, ledger=ledger, fail_after_send=fail_after_send),
        ),
        retry_policy=SEND_RETRY_POLICY,
    )
    builder.add_edge(START, "look_up_customer")
    builder.add_edge("look_up_customer", "triage_ticket")
    builder.add_edge("triage_ticket", "draft_reply")
    builder.add_edge("draft_reply", "check_policy")
    builder.add_conditional_edges(
        "check_policy",
        route_on_approval,
        {"escalate": "escalate", "auto_approve": "auto_approve"},
    )
    builder.add_edge("escalate", "send_reply")
    builder.add_edge("auto_approve", "send_reply")
    builder.add_edge("send_reply", END)
    return builder


def build_ticket_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    ledger: Optional[Ledger] = None,
    fail_after_send: int = 0,
    tracer: Optional[Tracer] = None,
):
    """Compile the graph, with a checkpointer it cannot do without and a ledger it should not.

    `None` does not mean "no checkpointer". The graph contains an `interrupt()`, and a pause has to
    be recorded somewhere or it cannot be resumed, so `None` means an `InMemorySaver`: memory that
    lasts as long as this process. Pass `sqlite_checkpointer(...)` when the run needs to outlive it.

    `ledger=None` behaves the same way and for the same reason, falling back to one in-memory ledger
    per process. The symmetry is worth pointing out when teaching: a run's *progress* and a run's
    *effects on the world* both need somewhere durable to live, they both default to somewhere that
    is not durable, and both defaults are fine right up until the process ends. Passing
    `sqlite_checkpointer(path)` and `Ledger.at(path)` together, on the same file, is the arrangement
    that actually survives a Saturday.

    `tracer=None`, Day 5's addition, means no spans: the compiled graph is exactly Day 4's. Pass a
    tracer from `build_tracer(...)` to get one span per node, and wrap the `invoke()`/`stream()` call
    in `run_span(...)` so those node spans share one trace. Off by default so tracing is a thing you
    switch on for a run you want to watch, never a tax on every run.
    """
    builder = ticket_graph_builder(
        ledger=ledger, fail_after_send=fail_after_send, tracer=tracer
    )
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


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
    ticket_text: str,
    customer_id: str,
    ticket_id: Optional[str] = None,
    refund_amount: float = 0.0,
) -> TicketState:
    """The starting state for one run.

    `customer`, `triage`, `draft_reply`, `approval`, `resolution` and `notes` start empty rather
    than absent, so a printed run shows every declared field from the first line, including the
    accumulating one before anything has accumulated into it.

    `refund_amount` is new and defaults to zero, which is the safe default rather than merely the
    convenient one: a ticket whose amount nobody supplied is worth nothing as far as the policy is
    concerned, so it cannot cross a threshold by accident. It arrives as an argument because it is a
    billing fact looked up alongside the ticket, not something any node in this graph derives.
    """
    return {
        "ticket_id": ticket_id or "",
        "ticket_text": ticket_text,
        "customer_id": customer_id,
        "refund_amount": float(refund_amount),
        "customer": {},
        "triage": {},
        "draft_reply": "",
        "approval": {},
        "resolution": {},
        "notes": [],
    }


def run_ticket_graph(
    ticket_text: str,
    customer_id: str,
    ticket_id: Optional[str] = None,
    refund_amount: float = 0.0,
) -> TicketState:
    """Run one ticket until the graph either finishes or stops to ask its approver.

    "Until" is doing real work in that sentence. A ticket the policy auto-approves runs all the way
    to `END`, sends its reply, and this returns the finished state. One that needs a human stops
    inside `escalate`, and what comes back is the state *plus* an `__interrupt__` key holding the
    question. Nothing raises, and `resolution` is simply still empty, so a caller that assumes a
    finished run will quietly get a half-finished one.

    That is not a wart to be smoothed over, it is what pausing looks like from the outside;
    `run_approval.py` exists to show it properly. Note that this helper uses the default in-memory
    ledger, so the run it starts can be resumed only inside this same process.
    """
    graph = build_ticket_graph()
    return graph.invoke(
        initial_state(ticket_text, customer_id, ticket_id, refund_amount),
        thread_config(ticket_id or "unnamed-run"),
    )
