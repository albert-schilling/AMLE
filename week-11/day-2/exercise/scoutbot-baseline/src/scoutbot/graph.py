"""ScoutBot's LangGraph graph: it chooses its path, survives a restart, waits, acts once, answers from a
source as hard or as lightly as the question deserves, and now remembers the customer across tickets.

**Week 9 Day 5 adds two nodes, `recall_memory` and `write_memory`, and one field, `recalled`.** Every
day before today made a single *run* smarter; each still began from nothing, so a returning customer was
a stranger. Today the graph gains a person-shaped memory. `recall_memory` runs right after the customer
lookup and pulls this customer's relevant past tickets out of a `MemoryStore` (Day 1's embedder and
vector-in-SQLite trick, scoped by `customer_id`), writing them into `recalled`. `draft_reply` hands those
lines to the model as *background* - used for continuity, never cited, so a grounded reply still cites
only policy. `write_memory` runs last, after the reply is sent, and stores one line about this ticket
keyed by `ticket_id` so a resumed or re-run ticket is remembered exactly once. Knowledge is what the
company knows and is cited; memory is what it remembers about *you* and is not. See `ticket_graph_builder`
for where the two new nodes sit.

**Week 9 Day 4 adds one node, `classify_query`, and a fork in front of retrieval.** Day 3 ran the
full formulate-retrieve-critique-reword loop on every ticket, including the ones that needed no
knowledge at all. Today a router runs after triage and picks a strategy - `direct` (skip retrieval,
answer from courtesy), `retrieve` (one search), or `iterative` (Day 3's full bounded loop) - and
`route_query` turns that choice into a path. It is the same conditional-routing idea as the approval
branch, applied to *how much retrieval to do*: adaptive RAG is retrieval effort matched to the
question. The loop, the grounding, the pause, the ledger are all Day 3's, untouched; the only new
work is one classifier call and one fork. See `ticket_graph_builder` for the shape.

**Week 9 Day 2 adds one node, `retrieve_knowledge`, and changes one, `draft_reply`.** Before today
the draft was written from the model's own recall, which is where "refunds take three to five days"
came from when the policy says five: nothing in the run had looked anything up. Now `retrieve_knowledge`
runs Day 1's `KnowledgeBase.search` over the ticket and writes the top passages into state, and
`draft_reply` hands those passages to the model as the *only* thing it may cite. That is the whole of
basic RAG in this graph: a retrieval step, then a generation step that is told to ground its answer in
what the retrieval found and to say so when it found nothing useful. There is no new framework and no
LangChain in the reply path; it is still the same Anthropic SDK, now with retrieved text in the prompt.

The retrieval score matters as much as the passages. `retrieve_knowledge` compares the top hit against
`knowledge.LOW_CONFIDENCE` and records when retrieval was weak, so a run keeps a visible note that the
corpus probably did not cover the question - the signal the agentic days build a re-query loop on.

Everything below this paragraph is the Week 8 graph, unchanged in shape except for the one inserted
node, and its narrative is kept because the guarantees it describes still hold.

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

from .core import classify_query, formulate_query, stream_reply, triage
from .knowledge import (
    LOW_CONFIDENCE,
    MAX_RETRIEVAL_ATTEMPTS,
    KnowledgeBase,
    fastembed_embedder,
    format_passages,
)
from .memory import MemoryStore, format_memories
from .notify import Ledger, send_reply
from .policy import approval_for_state, is_authorised
from .schema import QueryRoute
from .tracing import trace_node
from .tools import look_up_customer

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge_base"
"""Where the policy documents live, relative to this file: ``<solution root>/knowledge_base``.

Resolved from `__file__` rather than the working directory so a run started from anywhere finds the
corpus. It is only read by the lazy default knowledge base below; a caller that injects its own store
(every test does) never touches this path.
"""

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

    `retrieved` is Day 2's new field: the passages `retrieve_knowledge` found for this ticket, each a
    plain dict (`source`, `ordinal`, `text`, `score`) so the whole list survives the checkpointer as
    JSON. It sits in state rather than being passed straight to `draft_reply` for the same reason
    every other fact does - so a resumed or inspected run can show *what* the reply was grounded in,
    not just the reply.

    Three fields are Day 3's, and together they make retrieval a loop the agent drives rather than a
    single automatic step. `search_query` is what the agent decided to look up, which is no longer the
    raw ticket text but the policy topic underneath it. `tried_queries` accumulates (a reducer, like
    `notes`) every query the agent has tried, so a re-query can avoid repeating itself and the bound on
    attempts is just its length. `retrieval_ok` is the critique's verdict: whether the best passage
    cleared `LOW_CONFIDENCE`, and therefore whether the run drafts an answer or rewords the query and
    searches again.

    `route` is Day 4's one new field: the retrieval *strategy* the router chose for this ticket -
    `direct`, `retrieve`, or `iterative` (a `QueryRoute` value, stored as a plain string). It is
    written once by `classify_query` and read in two places: `route_query` uses it to decide whether
    to retrieve at all, and `route_after_critique` uses it to decide whether a `retrieve` ticket is
    allowed to reword (it is not - one search is the whole point of that strategy). One field is all
    that separates "answer this from courtesy" from "search once" from "search until it is good enough
    or the bound is spent".

    `recalled` is Day 5's one new field: this customer's past-ticket memories that matched the current
    ticket, each a plain dict (`ticket_id`, `text`, `score`) so the list survives the checkpointer as
    JSON. `recall_memory` writes it near the start of the run, from a `MemoryStore` scoped to the
    `customer_id`, and `draft_reply` reads it as background for the reply. It is retrieval's sibling and
    its opposite: also a semantic search over `float32` vectors, but over *this customer's* history rather
    than the shared corpus, and fed to the model as context to personalise rather than as a source to
    cite. Empty for a first-time customer, which is the honest default for a bot that has never met them.

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
    recalled: list[dict]
    triage: dict
    route: str
    search_query: str
    tried_queries: Annotated[list[str], operator.add]
    retrieved: list[dict]
    retrieval_ok: bool
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


_PROCESS_MEMORY: Optional[MemoryStore] = None


def _process_memory() -> MemoryStore:
    """One memory store per process, built the first time a node needs it and reused after.

    Same shape of default as `_process_kb()` and `_process_ledger()`: a caller that injects its own store
    (every test, and `run_memory.py`) never reaches this, and the ones that do not share a single
    in-memory instance. In-memory on purpose here - the process default remembers only within a process,
    exactly like the default ledger and the `InMemorySaver`. A script that wants memory to survive
    between runs passes `MemoryStore(embed, db_path=...)`, which is the whole point of the demo.

    The `fastembed_embedder()` call is the one place this default reaches the network, and only on the
    very first build in a machine's life, to download the model - and it is the *same* model the corpus
    uses, so memory adds no second download. Tests inject a store built with a fake embedder instead.
    """
    global _PROCESS_MEMORY
    if _PROCESS_MEMORY is None:
        _PROCESS_MEMORY = MemoryStore(fastembed_embedder())
    return _PROCESS_MEMORY


def recall_memory_node(state: TicketState, store: Optional[MemoryStore] = None) -> dict:
    """Day 5's first new node: pull what we already know about this customer, before drafting.

    It runs right after the customer lookup and searches the memory store for the entries most like the
    current ticket, scoped to this `customer_id`, and writes them into `recalled`. That is the whole of
    "cross-thread memory" in this graph: a semantic search, exactly like retrieval, but over one person's
    past tickets rather than the shared policy corpus, so a customer writing in for the third time about a
    refund arrives with the first two already in front of the draft.

    Nothing here grounds or cites - recalled memory is background, and `draft_reply` feeds it to the model
    as context for continuity, never as a source. A first-time customer, or one with nothing relevant in
    store, simply recalls an empty list, which is the honest and common case rather than an error.

    `store` is injected exactly like `kb`, `formulate` and `classify`: a parameter defaulting to the lazy
    process-wide `MemoryStore`, so a test passes a store built from a fake embedder and the graph never
    downloads a model to recall. The builder binds the real (or a caller's) store with `functools.partial`.
    """
    mem = store if store is not None else _process_memory()
    hits = mem.recall(state["customer_id"], state["ticket_text"])
    recalled = [{"ticket_id": h.ticket_id, "text": h.text, "score": h.score} for h in hits]
    if recalled:
        note = f"recalled {len(recalled)} past ticket(s) for {state['customer_id']}"
    else:
        note = f"no past tickets on file for {state['customer_id']}"
    return {"recalled": recalled, "notes": [note]}


def write_memory_node(state: TicketState, store: Optional[MemoryStore] = None) -> dict:
    """Day 5's second new node: remember this ticket, once, after the reply has gone out.

    It runs last, after `send_reply`, so it only records interactions the run actually completed. The
    memory it stores is one short line - the ticket text, its category, and how it resolved - keyed by
    `ticket_id`. The next ticket from this customer will embed near it and recall it.

    The `ticket_id` key is the idempotency guard, and it is deliberately the same discipline as the
    send-ledger's: this node sits at the end of a graph that can be resumed or re-run, and `MemoryStore.write`
    writing the same ticket twice would slowly fill recall with duplicates of one line. So the store
    dedupes on the ticket, and the note says whether this call actually wrote or found the memory already
    there - "acting once", applied to remembering.

    `store` is injected like every other component, defaulting to the process-wide memory.
    """
    mem = store if store is not None else _process_memory()
    triage = state.get("triage") or {}
    category = triage.get("category", "general")
    resolution = state.get("resolution") or {}
    outcome = resolution.get("path", "handled")
    text = f"{state['ticket_text'].strip()} (category: {category}; outcome: {outcome})"
    wrote = mem.write(state["customer_id"], state["ticket_id"], text)
    if wrote:
        note = f"remembered this ticket for {state['customer_id']}"
    else:
        note = f"already remembered {state['ticket_id'] or 'this ticket'}, nothing new written"
    return {"notes": [note]}


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


_ROUTE_NOTE = {
    QueryRoute.direct.value: "routed to a direct reply (no retrieval needed)",
    QueryRoute.retrieve.value: "routed to a single retrieval",
    QueryRoute.iterative.value: "routed to iterative retrieval",
}
"""What each route reads as in the run's notes, so a printed run says *why* it took its path."""


def classify_query_node(state: TicketState, classify=None) -> dict:
    """Day 4's new node: pick how much retrieval this ticket deserves, before any is done.

    This runs right after triage and before the retrieval loop, and its whole output is one field,
    `route`. Everything downstream reads it: `route_query` sends a `direct` ticket straight to the
    draft with no search at all, and sends `retrieve` and `iterative` into the loop, where
    `route_after_critique` then lets only the `iterative` one reword. That is adaptive RAG - the graph
    spends retrieval effort in proportion to what the question needs, instead of running the full loop
    on a "thanks, that's all!".

    `classify` is injected exactly like `formulate`, `kb` and `ledger`: a parameter defaulting to the
    real `core.classify_query`, so a test passes a deterministic stand-in and the graph never calls the
    model to check its own routing. The builder binds the real (or a caller's) function with
    `functools.partial`.
    """
    fn = classify if classify is not None else classify_query
    route = fn(state["ticket_text"])
    note = _ROUTE_NOTE.get(route, _ROUTE_NOTE[QueryRoute.iterative.value])
    return {"route": route, "notes": [note]}


def route_query(state: TicketState) -> str:
    """Turn the chosen strategy into the next node - the adaptive fork, and a plain function of state.

    Three exits: `direct` skips retrieval entirely and drafts from courtesy, while `retrieve` and
    `iterative` both enter the loop at `formulate_query` (they differ only later, in whether the
    critique may reword). An unknown or missing route falls back to `iterative`, the safe default: a
    router that failed should mean the agent searches *harder*, never that it skips the search on a
    real question. Like every router here it reads the decision another node already made, so it is
    testable with a hand-made dict and no graph.
    """
    route = state.get("route")
    if route in (QueryRoute.direct.value, QueryRoute.retrieve.value):
        return route
    return QueryRoute.iterative.value


_PROCESS_KB: Optional[KnowledgeBase] = None


def _process_kb() -> KnowledgeBase:
    """One knowledge base per process, built the first time a node needs it and reused after.

    Same shape of default as `_process_ledger()` below: a caller that supplies its own store never
    reaches this, and the ones that do not share a single lazily-built instance rather than paying to
    chunk and embed the corpus on every ticket. Built in memory from `CORPUS_DIR`, so it is fresh each
    process; a script that wants a persisted index passes `KnowledgeBase(embed, db_path=...)` in.

    The `fastembed_embedder()` call here is the one place in the whole graph that will reach the
    network, and only on the very first build in a machine's life, to download the embedding model.
    That is exactly why every test injects a store built with a fake embedder instead: nothing in the
    suite should download a model to check the wiring.
    """
    global _PROCESS_KB
    if _PROCESS_KB is None:
        _PROCESS_KB = KnowledgeBase.build(CORPUS_DIR, fastembed_embedder())
    return _PROCESS_KB


def formulate_query_node(state: TicketState, formulate=None) -> dict:
    """Day 3's first new node: let the agent decide what to search for.

    Before today, retrieval searched the raw ticket text, which is a person venting rather than a
    query. This node asks the model to name the policy topic underneath the ticket and writes that as
    `search_query` - the input to the retrieval "tool". That one indirection is what makes retrieval
    agentic: the agent chooses what to look up, and this same node is where it chooses *differently*
    the second time around.

    The node has two moods, and the difference is entirely in what is already in state. On the first
    pass `tried_queries` is empty, so `formulate` gets just the ticket and produces an opening query.
    On a loop back from the critique, `tried_queries` holds the queries that missed and `retrieved`
    holds their weak passages, so `formulate` is told what failed and asked to reword. The bound on how
    many times this can happen is simply `len(tried_queries)`, checked by the router, so nothing here
    counts.

    `formulate` is injected exactly like `kb` and `ledger`: a parameter defaulting to the real
    `core.formulate_query`, so a test passes a deterministic stand-in and the graph never calls the
    model to check its own wiring. The builder binds the real (or a caller's) function with
    `functools.partial`.
    """
    fn = formulate if formulate is not None else formulate_query
    tried = state.get("tried_queries") or []
    weak = format_passages(state.get("retrieved") or []) if tried else ""
    query = fn(state["ticket_text"], tried_queries=tried, weak_passages=weak)
    n = len(tried) + 1
    note = f"reworded the search (try {n}): {query!r}" if tried else f"search query: {query!r}"
    return {"search_query": query, "tried_queries": [query], "notes": [note]}


def retrieve_knowledge_node(
    state: TicketState, kb: Optional[KnowledgeBase] = None, *, k: int = 3
) -> dict:
    """Look the agent's chosen query up in the knowledge base.

    This is the retrieval half of RAG, and it is deliberately just a search plus a note. It searches
    `search_query` - what `formulate_query` decided the ticket is really asking - rather than the raw
    ticket text, falling back to the ticket only if nothing formed a query. It embeds that with the
    same model the corpus was indexed with (that sameness is non-negotiable, and it lives inside
    `KnowledgeBase.search`), takes the top `k` passages, and writes them into state as plain dicts so
    the checkpointer can serialise them, replacing whatever a previous attempt found.

    The one judgement it records is about *confidence*, not content: the best hit's cosine score
    against `LOW_CONFIDENCE`. It does not decide what to do about a weak score - that is the critique
    node's job - it just reports it, because a run that loops needs each attempt's score written down
    to be readable afterwards.

    `kb` is a parameter, not a module import, for the same reason `ledger` is on `send_reply`: it keeps
    this node a plain function a test can call with a hand-made store and no model anywhere. The builder
    binds the real (or a caller's) store with `functools.partial`; passing nothing falls back to the
    lazy process-wide base. `k` is keyword-only so the partial binds `kb` positionally without ever
    shadowing it.
    """
    store = kb if kb is not None else _process_kb()
    query = state.get("search_query") or state["ticket_text"]
    hits = store.search(query, k=k)
    best = hits[0].score if hits else 0.0
    retrieved = [
        {"source": h.source, "ordinal": h.ordinal, "text": h.text, "score": h.score}
        for h in hits
    ]
    if not hits:
        note = "retrieved nothing: the knowledge base is empty"
    elif best < LOW_CONFIDENCE:
        note = (
            f"retrieved {len(hits)} passages but the best only scored {best:.2f} "
            f"(under {LOW_CONFIDENCE}, so likely not covered)"
        )
    else:
        note = f"retrieved {len(hits)} passages (best [{hits[0].source}] at {best:.2f})"
    return {"retrieved": retrieved, "notes": [note]}


def critique_retrieval_node(state: TicketState) -> dict:
    """Day 3's second new node: judge whether the retrieval is good enough to answer from.

    The critique is deliberately cheap and deterministic: the best passage's score against
    `LOW_CONFIDENCE`. That is on purpose. The expensive, model-driven step is the *re-query*, and it
    should only run when a free check says it is needed, so the gate that decides whether to spend a
    model call is itself not a model call. It writes `retrieval_ok`, which the router reads.

    It also notices when the loop has run out of road. Once `tried_queries` has reached
    `MAX_RETRIEVAL_ATTEMPTS`, a weak result is no longer worth another try, and the note says so: the
    run will draft anyway, and the grounded prompt will turn that thin retrieval into "a teammate will
    follow up" rather than a guess. A richer critique - a model judging relevance, not just the score -
    is a natural extension and is left as one, because the score already carries the signal the day is
    built on.

    Day 4 gives the note one more case. On a single-shot `retrieve` route a weak result will *not*
    reword - one search is the whole strategy - so the note says "drafting anyway" rather than
    promising a re-query the router will never allow. The *verdict* (`retrieval_ok`) stays purely a
    function of the score; only the wording reads the route, so the printed run tells the truth about
    which way it is about to go.
    """
    hits = state.get("retrieved") or []
    best = hits[0]["score"] if hits else 0.0
    ok = best >= LOW_CONFIDENCE
    attempts = len(state.get("tried_queries") or [])
    single_shot = state.get("route") == QueryRoute.retrieve.value
    if ok:
        note = f"critique: retrieval is sufficient (best {best:.2f})"
    elif single_shot:
        note = f"critique: weak (best {best:.2f}); single-retrieval route, drafting anyway"
    elif attempts >= MAX_RETRIEVAL_ATTEMPTS:
        note = (
            f"critique: still weak after {attempts} tries (best {best:.2f}); "
            "drafting a decline"
        )
    else:
        note = f"critique: weak (best {best:.2f}); rewording and trying again"
    return {"retrieval_ok": ok, "notes": [note]}


def route_after_critique(state: TicketState) -> str:
    """Loop back to reword the query, or move on to draft - the whole agentic control flow.

    Three ways to leave the retrieval loop, one way to stay in it. Draft if the critique passed
    (`retrieval_ok`); draft if this ticket was routed to a single `retrieve` and has had its one
    search, because rewording is exactly the effort that route chose *not* to spend; draft if the
    agent has already used its `MAX_RETRIEVAL_ATTEMPTS` and a further reword would only reach the same
    decline. Otherwise - a weak result, on the `iterative` route, with tries to spare - reword and
    search again.

    Day 4's one change is the `retrieve` clause: the same critique still runs and still labels the
    confidence honestly, but a single-shot ticket does not get to loop on a miss. An ordinary function
    of the state, so all three exits are testable with a hand-made dict and no graph.
    """
    if state.get("retrieval_ok"):
        return "draft_reply"
    if state.get("route") == QueryRoute.retrieve.value:
        return "draft_reply"
    if len(state.get("tried_queries") or []) >= MAX_RETRIEVAL_ATTEMPTS:
        return "draft_reply"
    return "reformulate"


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

    **Day 2's change lives in one argument.** The passages `retrieve_knowledge` wrote into state are
    formatted with `format_passages` and handed to `stream_reply` as `knowledge`. That is the switch
    from a recalled reply to a grounded one: the prompt now carries the policy text the answer must
    come from, and the model is told to cite it and to decline when it is thin. Everything else about
    this node - the writer, the streaming, the note - is untouched, which is the honest scale of
    "adding RAG" to a graph that already retrieves: a formatter and a keyword argument.
    """
    context = (
        f"Triaged as {state['triage'].get('category')} / "
        f"{state['triage'].get('priority')} priority."
    )
    knowledge = format_passages(state.get("retrieved") or [])
    # Day 5: recalled memory rides in as `memory`, a separate argument from `knowledge`. It personalises
    # the reply (continuity with past tickets) without grounding it, and is never cited, so a `direct`
    # reply with no passages can still read as "good to hear from you again" while a grounded one still
    # cites only policy. When `recalled` is empty this is byte-for-byte Day 4's call.
    memory = format_memories(state.get("recalled") or [])
    text = stream_reply(
        state["ticket_text"],
        on_chunk=lambda chunk: writer({"draft_chunk": chunk}),
        context=context,
        knowledge=knowledge,
        memory=memory,
    )
    note = "drafted a grounded reply" if knowledge else "drafted a reply"
    return {"draft_reply": text, "notes": [note]}


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
    kb: Optional[KnowledgeBase] = None,
    formulate=None,
    classify=None,
    memory: Optional[MemoryStore] = None,
) -> StateGraph:
    """The graph's shape, un-compiled.

        START -> look_up_customer -> recall_memory -> triage_ticket -> classify_query
              -> (direct: ------------------------------------------------> draft_reply)
              -> (retrieve | iterative: formulate_query -> retrieve_knowledge
                    -> critique_retrieval -> (reformulate: back to formulate_query | draft_reply))
              -> draft_reply -> check_policy -> (escalate | auto_approve)
              -> send_reply -> write_memory -> END

    **Week 9 Day 5 wraps the run in memory.** `recall_memory` goes in right after the customer lookup, so
    every route - even a `direct` "thanks!" - has this customer's relevant past tickets in `recalled`
    before it drafts. `write_memory` goes in right after `send_reply`, so a ticket is remembered only once
    it is truly done, and keyed by `ticket_id` so a resumed or re-run ticket is remembered once. Neither
    touches the retrieval loop or the approval branch; memory brackets the existing graph rather than
    threading through it. `memory` is injected exactly like `kb`, `formulate` and `classify`: `None` means
    the lazy process-wide store, and a test passes a store built from a fake embedder so recall and write
    happen with no model. The one cycle in the graph is still `critique_retrieval -> formulate_query`;
    memory adds none.

    **Week 9 Day 4 puts a router in front of retrieval.** A new `classify_query` node runs after
    triage and picks a strategy - `direct`, `retrieve`, or `iterative` - which `route_query` turns
    into a path. `direct` skips the loop entirely and drafts from courtesy (no search, no citation);
    `retrieve` and `iterative` both enter Day 3's loop at `formulate_query`, and differ only at
    `route_after_critique`, which lets `iterative` reword a weak result but sends a single-shot
    `retrieve` straight to the draft. That is adaptive RAG: retrieval effort matched to the question,
    rather than every ticket paying for the full loop. `classify` is injected exactly like `formulate`
    and `kb`; tests pass a deterministic stand-in so routing is checked without a model. The graph
    still has exactly one cycle - `critique_retrieval -> formulate_query` - because the two retrieval
    routes share it and `direct` never touches it.

    **Week 9 Day 3 turns retrieval into a loop.** Day 2's single `retrieve_knowledge` node becomes a
    three-node cycle: `formulate_query` decides what to search for, `retrieve_knowledge` searches it,
    and `critique_retrieval` judges the result. `route_after_critique` then either drafts (the passages
    are good enough, or the attempt bound is spent) or loops back to `formulate_query` to reword and
    try again. That back-edge is the only cycle in the graph, and it is safe because it is bounded by
    `MAX_RETRIEVAL_ATTEMPTS`. `formulate` is injected like `kb`: `None` means the real
    `core.formulate_query`; tests pass a deterministic stand-in so the loop is checked without a model.

    Week 9 Day 2 inserted `retrieve_knowledge` between triage and drafting, and bound the knowledge
    base into it with `functools.partial` exactly as `send_reply` binds its ledger. A `kb` of `None`
    is not "no retrieval": the node falls back to the lazy process-wide base, the same way a `None`
    checkpointer means an `InMemorySaver`. Tests pass a store built from a fake embedder so the wiring
    is checked without a model.

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
    builder.add_node(
        "recall_memory", node("recall_memory", partial(recall_memory_node, store=memory))
    )
    builder.add_node("triage_ticket", node("triage_ticket", triage_ticket_node))
    builder.add_node(
        "classify_query",
        node("classify_query", partial(classify_query_node, classify=classify)),
    )
    builder.add_node(
        "formulate_query",
        node("formulate_query", partial(formulate_query_node, formulate=formulate)),
    )
    builder.add_node(
        "retrieve_knowledge",
        node("retrieve_knowledge", partial(retrieve_knowledge_node, kb=kb)),
    )
    builder.add_node(
        "critique_retrieval", node("critique_retrieval", critique_retrieval_node)
    )
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
    builder.add_node(
        "write_memory", node("write_memory", partial(write_memory_node, store=memory))
    )
    builder.add_edge(START, "look_up_customer")
    builder.add_edge("look_up_customer", "recall_memory")
    builder.add_edge("recall_memory", "triage_ticket")
    builder.add_edge("triage_ticket", "classify_query")
    builder.add_conditional_edges(
        "classify_query",
        route_query,
        {
            QueryRoute.direct.value: "draft_reply",
            QueryRoute.retrieve.value: "formulate_query",
            QueryRoute.iterative.value: "formulate_query",
        },
    )
    builder.add_edge("formulate_query", "retrieve_knowledge")
    builder.add_edge("retrieve_knowledge", "critique_retrieval")
    builder.add_conditional_edges(
        "critique_retrieval",
        route_after_critique,
        {"reformulate": "formulate_query", "draft_reply": "draft_reply"},
    )
    builder.add_edge("draft_reply", "check_policy")
    builder.add_conditional_edges(
        "check_policy",
        route_on_approval,
        {"escalate": "escalate", "auto_approve": "auto_approve"},
    )
    builder.add_edge("escalate", "send_reply")
    builder.add_edge("auto_approve", "send_reply")
    builder.add_edge("send_reply", "write_memory")
    builder.add_edge("write_memory", END)
    return builder


def build_ticket_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    ledger: Optional[Ledger] = None,
    fail_after_send: int = 0,
    tracer: Optional[Tracer] = None,
    kb: Optional[KnowledgeBase] = None,
    formulate=None,
    classify=None,
    memory: Optional[MemoryStore] = None,
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
        ledger=ledger,
        fail_after_send=fail_after_send,
        tracer=tracer,
        kb=kb,
        formulate=formulate,
        classify=classify,
        memory=memory,
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

    Every field except the four inputs starts empty rather than absent - `customer`, `recalled`,
    `triage`, `route`, `search_query`, `tried_queries`, `retrieved`, `retrieval_ok`, `draft_reply`,
    `approval`, `resolution`, `notes` - so a printed run shows every declared field from the first line,
    including the accumulating ones before anything has accumulated into them.

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
        "recalled": [],
        "triage": {},
        "route": "",
        "search_query": "",
        "tried_queries": [],
        "retrieved": [],
        "retrieval_ok": False,
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
