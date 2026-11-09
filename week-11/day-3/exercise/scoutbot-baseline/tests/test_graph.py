"""These tests patch the Anthropic SDK boundary directly (`scoutbot.core._client`), so they run
offline - no real API key or network access needed, same pattern as every earlier day. The graph
itself needs no mocking: LangGraph runs entirely locally, and `look_up_customer` reads the
repo's own `mock_customers.json`.

What's worth testing on a day about state is not "does the model answer correctly" but the state
mechanics themselves: that a node's partial return gets merged rather than replacing everything,
that the reducer field accumulates while plain fields do not, and that the second node genuinely
sees what the first one wrote instead of being handed the ticket text directly.

Day 2 added two groups of cases. The router ones need no mocking at all, since a router is a plain
function of a hand-made state dict. The checkpointer ones use a real SQLite file in pytest's
`tmp_path` and open a *second* connection to it to resume, which is as close to "a different
process" as an in-process test can honestly get; `run_resume.py` is what demonstrates the real
thing across two shells.

Day 3 changed the shape of many of these, because a ticket that needs a human no longer *finishes*:
it stops inside `escalate` and waits. A run that pauses comes back with an `__interrupt__` key and an
empty `resolution`, which is why several assertions here are about a run being unfinished. And
`messages.stream` needs faking alongside `messages.create`, since `draft_reply` makes a second,
streamed model call.

Day 4 changes them again, in three ways worth knowing before reading the diff:

- **Every branch now ends at `send_reply`**, so a finished run has one more note than it used to and
  the last one is always about the email. The two arms of the branch rejoin rather than each running
  to `END`.
- **The router reads a decision rather than making one.** `route_on_approval` replaces
  `route_after_triage`, and the interesting cases moved to `tests/test_policy.py`, where they need
  neither a graph nor a mock.
- **`send_reply` is not idempotent by itself**, so these tests have to be careful about the ledger.
  The autouse fixture below resets the process-wide one between tests, because without it the second
  test to use a given ticket ID would find its own predecessor's row and skip the send. That is the
  guarantee working correctly and it would look like a broken test, which is worth seeing once.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from scoutbot import graph as graph_module
from scoutbot import notify
from scoutbot.graph import (
    TicketState,
    build_ticket_graph,
    check_policy_node,
    classify_query_node,
    critique_retrieval_node,
    draft_reply_node,
    formulate_query_node,
    initial_state,
    look_up_customer_node,
    retrieve_knowledge_node,
    route_after_critique,
    route_on_approval,
    route_query,
    run_ticket_graph,
    send_reply_node,
    sqlite_checkpointer,
    thread_config,
    ticket_graph_builder,
)
from scoutbot.knowledge import MAX_RETRIEVAL_ATTEMPTS, Chunk, KnowledgeBase
from scoutbot.memory import MemoryStore
from scoutbot.notify import Ledger
from scoutbot.schema import QueryRoute

# A hand-written embedder over four keyword axes, same trick as tests/test_knowledge.py: a text is
# placed on the axes whose words it contains, so a "charged twice" billing ticket points along the
# billing axis and retrieves the billing chunk, all with no model and no download. Day 2's graph runs
# `retrieve_knowledge` on every ticket, so without an injected store like this the suite would try to
# fetch a real embedding model - exactly what the "inject the thing that needs the network" rule is
# for.
_AXES = ["refund", "shipping", "warranty", "billing"]
_AXIS_WORDS = {
    "refund": ("refund", "refunds", "money", "returned"),
    "shipping": ("shipping", "delivery", "deliver", "ship"),
    "warranty": ("warranty", "broken", "defect", "defective"),
    "billing": ("billing", "charged", "charge", "duplicate", "twice", "invoice"),
}


def keyword_embedder(texts):
    import numpy as np

    vecs = []
    for text in texts:
        low = text.lower()
        vec = np.array(
            [1.0 if any(w in low for w in _AXIS_WORDS[axis]) else 0.0 for axis in _AXES],
            dtype=np.float32,
        )
        if not vec.any():
            vec = np.ones(len(_AXES), dtype=np.float32)  # equally unlike everything -> ties at 0.5
        vecs.append(vec)
    return vecs


def _fake_kb() -> KnowledgeBase:
    """A four-passage store built with the keyword embedder, in a fixed insertion order.

    The order matters only for the tie-break: when a ticket matches no axis every passage scores 0.5
    and `argsort` returns them in insertion order, so `refunds` is the reported top of a tie. A ticket
    that does match an axis (the billing ones most tests use) retrieves that passage at a clean 1.0.
    """
    kb = KnowledgeBase(keyword_embedder)
    kb.index(
        [
            Chunk("refunds", 0, "refunds are issued within five business days"),
            Chunk("shipping", 0, "shipping is free over fifty euros"),
            Chunk("warranty", 0, "the warranty covers manufacturing defects"),
            Chunk("billing", 0, "a duplicate charge is reversed within two days"),
        ]
    )
    return kb


def echo_formulate(ticket_text, tried_queries=(), weak_passages=""):
    """A stand-in for `core.formulate_query` that echoes the ticket text as the search query.

    Day 3's graph runs `formulate_query` on every ticket, and the real one is a model call. Injecting
    this keeps the suite offline the same way the fake knowledge base does, and echoing the ticket
    means retrieval searches exactly what Day 2 searched, so the keyword embedder still lands the
    billing ticket on the billing passage. Tests about the *loop* pass their own fake that changes its
    answer between tries.
    """
    return ticket_text


def route_iterative(ticket_text):
    """A stand-in for `core.classify_query` that always chooses the full loop.

    Day 4's graph runs `classify_query` on every ticket, and the real one is a model call. Defaulting
    the fixture to `iterative` keeps every earlier test's path unchanged - the retrieval loop still
    runs on every ticket exactly as it did on Day 3 - while spending no `messages.create` on routing,
    so the call-count assertions stay honest. Tests about the *router itself* pass their own fake that
    returns `direct` or `retrieve`.
    """
    return QueryRoute.iterative.value

VALID_TRIAGE = {"category": "billing", "priority": "high", "suggested_owner": "billing-team"}
LOW_TRIAGE = {"category": "technical", "priority": "low", "suggested_owner": "support-team"}

DRAFT_CHUNKS = ["Thanks for flagging this. ", "We're looking into the duplicate charge now."]
DRAFT_TEXT = "".join(DRAFT_CHUNKS)

# The note `check_policy` writes for a zero-amount, high-priority ticket on a clean account: no
# threshold is crossed, so it is the triage priority that pulls a person in.
POLICY_NOTE_HIGH = "policy: needs support_lead (triaged high priority, so a person should see it)"
POLICY_NOTE_NONE = (
    "policy: no human needed (EUR 0.00 on a clean account, under every threshold)"
)

# What `retrieve_knowledge` writes for a "charged twice" ticket against the fake store: the billing
# passage is a clean axis match, so it scores 1.0 and is named as the top hit.
RETRIEVE_NOTE_BILLING = "retrieved 3 passages (best [billing] at 1.00)"

# Day 3's two new notes for that same billing ticket: the agent's search query (the echo fake returns
# the ticket text), and the critique passing because the billing passage clears the confidence floor.
QUERY_NOTE_BILLING = "search query: 'I was charged twice.'"
CRITIQUE_NOTE_OK = "critique: retrieval is sufficient (best 1.00)"

# Day 4's new note: the router's choice. The fixture defaults every ticket to the iterative strategy,
# so this is the note the pre-Day-4 tests grow.
ROUTE_NOTE_ITERATIVE = "routed to iterative retrieval"

# Day 5's two new notes for a customer the fixture's empty store has never seen: recall (right after
# the customer lookup) finds nothing, and write (right after the send) stores this ticket for the
# first time. A run that pauses at `escalate` shows only the recall note, since `write_memory` is past
# the send.
RECALL_NOTE_NONE_1001 = "no past tickets on file for 1001"
WRITE_NOTE_1001 = "remembered this ticket for 1001"


@pytest.fixture(autouse=True)
def _fresh_ledger():
    """Give every test its own empty ledger, flaky-attempt counter, knowledge base and query maker.

    The ledger and the counter live at module level in the code under test, deliberately: a guarantee
    about repeated calls has to outlive the calls, so it cannot be a local. That makes them shared
    state between tests, so they get reset here rather than leaking.

    `_PROCESS_KB` is seeded rather than reset: Day 2's graph retrieves on every ticket, so this points
    the lazy process-wide store at the offline fake above. Any test that builds a graph without an
    explicit `kb=` therefore retrieves from the fake instead of downloading a model.

    `graph.formulate_query` is patched to the echo fake for the same reason: Day 3's graph calls it on
    every ticket, and the real one is a model call. Patching the module global means a graph built
    without an explicit `formulate=` uses the offline echo, so `messages.create` is called only by
    triage and the call-count assertions stay honest. A test that wants the real re-query behaviour
    passes its own fake through `build_ticket_graph(formulate=...)`.

    `graph.classify_query` is patched the same way, and for the same reason - Day 4's graph routes
    every ticket through a model call. Defaulting it to `route_iterative` keeps every earlier test's
    path exactly as it was (the loop still runs on every ticket) and spends no `messages.create` on
    routing. A test about the router passes its own fake through `build_ticket_graph(classify=...)`.

    `_PROCESS_MEMORY` is seeded rather than reset, exactly like `_PROCESS_KB`: Day 5's graph recalls
    and writes memory on every ticket, so this points the lazy process-wide store at a `MemoryStore`
    built on the offline keyword embedder. A graph built without an explicit `memory=` therefore
    recalls and writes with no download, and because each test gets a *fresh* empty store, one test's
    written memory never leaks into another's recall.
    """
    graph_module._PROCESS_LEDGER = None
    graph_module._PROCESS_KB = _fake_kb()
    graph_module._PROCESS_MEMORY = MemoryStore(keyword_embedder)
    _real_formulate = graph_module.formulate_query
    graph_module.formulate_query = echo_formulate
    _real_classify = graph_module.classify_query
    graph_module.classify_query = route_iterative
    notify.reset_flaky_counter()
    yield
    graph_module._PROCESS_LEDGER = None
    graph_module._PROCESS_KB = None
    graph_module._PROCESS_MEMORY = None
    graph_module.formulate_query = _real_formulate
    graph_module.classify_query = _real_classify
    notify.reset_flaky_counter()


def _fake_response(input_dict: dict = None):
    """Mimics an Anthropic Message response carrying one tool_use block, same helper shape as
    tests/test_triage.py."""
    block = SimpleNamespace(
        type="tool_use", name="triage_ticket", input=input_dict or VALID_TRIAGE
    )
    return SimpleNamespace(content=[block])


class _FakeStream:
    """Mimics `client.messages.stream(...)`: a context manager exposing `.text_stream`.

    Two chunks rather than one, so a test can tell "streamed in pieces" apart from "returned all
    at once", which is the whole claim `draft_reply_node` makes.
    """

    def __init__(self, chunks=None):
        self._chunks = chunks or DRAFT_CHUNKS

    def __enter__(self):
        return SimpleNamespace(text_stream=iter(self._chunks))

    def __exit__(self, *exc_info):
        return False


def _wire(mock_client, triage_input: dict = None):
    """Point both model calls at fakes: `create` for triage, `stream` for the draft."""
    mock_client.return_value.messages.create.return_value = _fake_response(triage_input)
    mock_client.return_value.messages.stream.return_value = _FakeStream()
    return mock_client.return_value.messages


def _boom(state):
    """Stands in for the box being restarted, once triage has already completed and been saved.

    A plain function rather than a `Mock`, because LangGraph inspects a node's signature to work
    out what to pass it. Note that swapping this in also removes the `interrupt()` from the graph,
    which is exactly what the crash tests want: a run that dies, not one that pauses politely.
    """
    raise RuntimeError("the box restarted")


@patch("scoutbot.core._client")
def test_graph_runs_its_nodes_and_fills_every_declared_field(mock_client):
    _wire(mock_client)

    final = run_ticket_graph("I was charged twice.", customer_id="1001", ticket_id="T-3001")

    assert final["customer"]["found"] is True
    assert final["customer"]["plan"] == "pro"
    assert final["triage"] == VALID_TRIAGE
    assert final["draft_reply"] == DRAFT_TEXT
    assert final["approval"]["needs_human"] is True
    # Inputs are carried through untouched - no node returned them, so nothing overwrote them.
    assert final["ticket_id"] == "T-3001"
    assert final["customer_id"] == "1001"


@patch("scoutbot.core._client")
def test_notes_accumulate_across_nodes_because_of_the_reducer(mock_client):
    """`notes` is `Annotated[list[str], operator.add]`, so each node's list is appended to what is
    already there rather than replacing it. Without the reducer this would be length 1.

    Nine notes: this run stops at the pause, so neither `escalate`, `send_reply` nor `write_memory`
    has written anything yet. Day 5 adds the recall note right after the customer lookup (an empty
    store, so "no past tickets"); Day 4's router choice, Day 3's search query and passing critique
    follow; the draft note still says grounded, because the billing passage cleared the floor on the
    first try.
    """
    _wire(mock_client)

    final = run_ticket_graph("I was charged twice.", customer_id="1001")

    assert final["notes"] == [
        "looked up 1001: found",
        RECALL_NOTE_NONE_1001,
        "triaged as billing/high",
        ROUTE_NOTE_ITERATIVE,
        QUERY_NOTE_BILLING,
        RETRIEVE_NOTE_BILLING,
        CRITIQUE_NOTE_OK,
        "drafted a grounded reply",
        POLICY_NOTE_HIGH,
    ]


@patch("scoutbot.core._client")
def test_plain_field_is_replaced_not_merged(mock_client):
    """`customer` has no reducer, so the node's record replaces the empty dict it started as,
    instead of being merged into it."""
    _wire(mock_client)
    start = initial_state("I was charged twice.", customer_id="1001")
    start["customer"] = {"stale": "should be gone"}

    final = build_ticket_graph().invoke(start, thread_config("T-plain"))

    assert "stale" not in final["customer"]
    assert final["customer"]["customer_id"] == "1001"


@patch("scoutbot.core._client")
def test_second_node_reads_what_the_first_node_wrote(mock_client):
    """The triage node must build its prompt from state, not from the ticket text alone - the
    looked-up record has to reach the model, or shared state is decorative."""
    messages = _wire(mock_client)

    run_ticket_graph("I was charged twice.", customer_id="1001")

    prompt = messages.create.call_args.kwargs["messages"][0]["content"]
    assert "I was charged twice." in prompt
    assert "Customer record:" in prompt
    assert '"plan": "pro"' in prompt


@patch("scoutbot.core._client")
def test_streaming_yields_one_update_per_node_in_order(mock_client):
    """`stream_mode="updates"` is how the live lesson shows state changing: one chunk per node,
    keyed by node name, containing only that node's own fields.

    The last chunk is not a node at all. `__interrupt__` is how a pause arrives on this stream.
    """
    _wire(mock_client)
    graph = build_ticket_graph()

    chunks = list(
        graph.stream(
            initial_state("I was charged twice.", "1001"),
            thread_config("T-order"),
            stream_mode="updates",
        )
    )

    assert [name for chunk in chunks for name in chunk] == [
        "look_up_customer",
        "recall_memory",
        "triage_ticket",
        "classify_query",
        "formulate_query",
        "retrieve_knowledge",
        "critique_retrieval",
        "draft_reply",
        "check_policy",
        "__interrupt__",
    ]
    assert set(chunks[0]["look_up_customer"]) == {"customer", "notes"}
    assert set(chunks[1]["recall_memory"]) == {"recalled", "notes"}
    assert set(chunks[2]["triage_ticket"]) == {"triage", "notes"}
    assert set(chunks[3]["classify_query"]) == {"route", "notes"}
    assert set(chunks[4]["formulate_query"]) == {"search_query", "tried_queries", "notes"}
    assert set(chunks[5]["retrieve_knowledge"]) == {"retrieved", "notes"}
    assert set(chunks[6]["critique_retrieval"]) == {"retrieval_ok", "notes"}
    assert set(chunks[8]["check_policy"]) == {"approval", "notes"}


@patch("scoutbot.core._client")
def test_unknown_customer_still_reaches_the_triage_node(mock_client):
    """The branch is on the policy decision, not on the lookup: a missing customer record is
    written into state like any other result, and the graph carries straight on to triage."""
    _wire(mock_client)

    final = run_ticket_graph("Who am I?", customer_id="does-not-exist")

    assert final["customer"] == {"found": False, "customer_id": "does-not-exist"}
    assert final["notes"][0] == "looked up does-not-exist: not found"
    assert final["triage"] == VALID_TRIAGE


def test_node_returns_only_the_fields_it_changed():
    """Called directly, outside any graph: a node is a plain function from state to a partial
    update. Nothing about it needs LangGraph to be understood or tested."""
    state: TicketState = initial_state("Some ticket", customer_id="1001")

    update = look_up_customer_node(state)

    assert set(update) == {"customer", "notes"}
    assert "ticket_text" not in update


# --- The approval policy, as the graph sees it ----------------------------------------------
# The policy table itself is exhaustively tested in tests/test_policy.py, with no graph and no
# mock anywhere. These cases are only about the two places the graph touches it: the node that
# records the decision, and the router that reads it.


def test_check_policy_records_the_decision_and_the_rule_behind_it():
    """The decision goes into state so it can be explained later, not just acted on now."""
    state = initial_state("I want a refund.", "1001", "T-policy", refund_amount=900.0)
    state["customer"] = {"plan": "pro", "past_refunds_90d": 2}
    state["triage"] = VALID_TRIAGE

    update = check_policy_node(state)

    assert update["approval"]["needs_human"] is True
    assert update["approval"]["approver"] == "billing_manager"
    assert "900.00" in update["approval"]["reason"]
    assert "billing_manager" in update["notes"][0]


def test_the_router_only_reads_the_decision_it_was_given():
    """`route_on_approval` is deliberately dumber than Day 2's router: the judgement moved into a
    pure function, leaving this to do one thing."""
    state = initial_state("I want a refund.", customer_id="1001")

    state["approval"] = {"needs_human": True, "approver": "billing_manager"}
    assert route_on_approval(state) == "escalate"

    state["approval"] = {"needs_human": False, "approver": "scoutbot"}
    assert route_on_approval(state) == "auto_approve"


@patch("scoutbot.core._client")
def test_a_large_refund_needs_a_billing_manager_end_to_end(mock_client):
    """The whole first topic in one run: the amount decides who is asked."""
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-big")

    final = graph.invoke(
        initial_state("I want a refund.", "1001", "T-big", refund_amount=900.0), config
    )

    assert final["approval"]["approver"] == "billing_manager"
    assert final["__interrupt__"][0].value["approver_required"] == "billing_manager"


@patch("scoutbot.core._client")
def test_a_ticket_that_needs_a_human_stops_at_the_escalate_node(mock_client):
    """The escalate branch does not finish the run, it suspends it."""
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-high")

    final = graph.invoke(initial_state("I was charged twice.", "1001", "T-high"), config)

    assert "__interrupt__" in final
    assert final["resolution"] == {}
    assert graph.get_state(config).next == ("escalate",)


@patch("scoutbot.core._client")
def test_a_ticket_the_policy_clears_runs_all_the_way_through_and_sends(mock_client):
    """The branch not taken leaves no trace at all: only one terminal node ever writes
    `resolution`, so its value doubles as a record of which way the run went.

    This branch has no `interrupt()` in it, so it still runs start to finish in one call - and
    unlike Day 3, it now ends by actually sending something.
    """
    _wire(mock_client, LOW_TRIAGE)

    final = run_ticket_graph("How do I export a CSV?", customer_id="1001", ticket_id="T-low")

    assert "__interrupt__" not in final
    assert final["approval"]["needs_human"] is False
    assert final["resolution"]["path"] == "auto_approved"
    assert final["resolution"]["reviewed_by"] == "scoutbot"
    # `write_memory` runs after `send_reply` now, so the send note is second-to-last and the run ends
    # by remembering the ticket.
    assert final["notes"][-2] == "reply sent to the customer (ledger key T-low:send_reply)"
    assert final["notes"][-1] == WRITE_NOTE_1001


# --- Streaming the work as it happens ------------------------------------------------------


@patch("scoutbot.core._client")
def test_draft_chunks_arrive_as_custom_events_before_the_node_finishes(mock_client):
    """The streaming half of Day 3, in one assertion about ordering.

    Every piece of the draft arrives as its own `custom` event, and all of them arrive *before*
    the `updates` chunk for `draft_reply`. That ordering is the claim: output exists while the
    node is still working, not only once it has returned.
    """
    _wire(mock_client)
    graph = build_ticket_graph()

    seen = []
    for mode, chunk in graph.stream(
        initial_state("I was charged twice.", "1001", "T-stream"),
        thread_config("T-stream"),
        stream_mode=["updates", "custom"],
    ):
        if mode == "custom":
            seen.append(("chunk", chunk["draft_chunk"]))
        else:
            seen.append(("node", next(iter(chunk))))

    assert ("chunk", DRAFT_CHUNKS[0]) in seen
    assert ("chunk", DRAFT_CHUNKS[1]) in seen
    assert seen.index(("chunk", DRAFT_CHUNKS[-1])) < seen.index(("node", "draft_reply"))


@patch("scoutbot.core._client")
def test_the_streaming_node_is_still_an_ordinary_function(mock_client):
    """Day 1's best property, deliberately kept: no graph, no stream, just a call.

    This is the payoff for taking `writer` as a parameter rather than calling
    `get_stream_writer()` inside the node. The docs' version of this node raises
    `RuntimeError: Called get_config outside of a runnable context` here.
    """
    _wire(mock_client)
    state = initial_state("I was charged twice.", "1001")
    state["triage"] = VALID_TRIAGE

    update = draft_reply_node(state)

    assert update["draft_reply"] == DRAFT_TEXT
    assert update["notes"] == ["drafted a reply"]


@patch("scoutbot.core._client")
def test_a_test_can_collect_the_events_a_node_emits_without_a_graph(mock_client):
    """And the second payoff: what the node emitted is assertable directly."""
    _wire(mock_client)
    state = initial_state("I was charged twice.", "1001")
    state["triage"] = VALID_TRIAGE
    collected = []

    draft_reply_node(state, collected.append)

    assert collected == [{"draft_chunk": chunk} for chunk in DRAFT_CHUNKS]


@patch("scoutbot.core._client")
def test_the_draft_prompt_carries_the_triage_result_and_the_passages(mock_client):
    """Same lesson as the triage node's prompt: a later node reads what an earlier one wrote.

    Day 2 adds the retrieved passages to the same prompt. The billing ticket retrieves the billing
    passage from the fake store, so the drafting call carries both the triage context and the policy
    text - tagged `[billing]`, the exact citation shape the grounded system prompt asks for back.
    """
    messages = _wire(mock_client)

    run_ticket_graph("I was charged twice.", customer_id="1001")

    prompt = messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "I was charged twice." in prompt
    assert "billing" in prompt
    assert "high priority" in prompt
    assert "[billing] a duplicate charge is reversed within two days" in prompt


# --- Retrieval-augmented drafting (Day 2) --------------------------------------------------
# The retrieval mechanics themselves are tested offline in tests/test_knowledge.py. These cases are
# about the two graph pieces: the node that searches and records, and the draft node reading what it
# wrote and grounding the model on it.


def test_retrieve_knowledge_node_ranks_writes_dicts_and_notes_confidence():
    """Called directly with a hand-made store: a plain function from state to a partial update.

    It writes JSON-serialisable dicts (not `Retrieved` objects) so the checkpointer can persist them,
    ranks the on-topic passage first, and records the top score in its note.
    """
    state = initial_state("my card was charged twice for one order", "1001", "T-ret")

    update = retrieve_knowledge_node(state, kb=_fake_kb())

    assert set(update) == {"retrieved", "notes"}
    assert [type(p) for p in update["retrieved"]] == [dict, dict, dict]
    assert update["retrieved"][0]["source"] == "billing"
    assert update["retrieved"][0]["score"] == pytest.approx(1.0)
    assert update["notes"] == ["retrieved 3 passages (best [billing] at 1.00)"]


def test_retrieve_knowledge_node_flags_a_low_confidence_miss():
    """A question the corpus does not cover retrieves *something* - the closest row - but says so.

    The one-passage store is about refunds; the query is about billing, an orthogonal axis, so the top
    score is 0.0 and the note names it as under the threshold. This is the signal Day 2's grounded
    draft turns into a refusal, and the hook the agentic days build a re-query loop on.
    """
    kb = KnowledgeBase(keyword_embedder)
    kb.index([Chunk("refunds", 0, "refunds are issued within five business days")])
    state = initial_state("why was my card charged twice", "1001", "T-miss")

    update = retrieve_knowledge_node(state, kb=kb)

    assert update["retrieved"][0]["source"] == "refunds"
    assert update["retrieved"][0]["score"] == pytest.approx(0.0)
    assert update["notes"] == [
        "retrieved 1 passages but the best only scored 0.00 (under 0.5, so likely not covered)"
    ]


@patch("scoutbot.core._client")
def test_draft_grounds_on_passages_and_switches_to_the_grounded_system_prompt(mock_client):
    """The generation half of RAG, asserted at the SDK boundary.

    When state carries retrieved passages, the draft call uses `GROUNDED_DRAFT_SYSTEM` (cite, and
    decline when thin) rather than the ungrounded one, and the passages are in the user message.
    """
    from scoutbot.core import GROUNDED_DRAFT_SYSTEM

    messages = _wire(mock_client)
    state = initial_state("I was charged twice.", "1001", "T-ground")
    state["triage"] = VALID_TRIAGE
    state["retrieved"] = [
        {"source": "billing", "ordinal": 0, "text": "a duplicate charge is reversed", "score": 1.0}
    ]

    update = draft_reply_node(state)

    assert messages.stream.call_args.kwargs["system"] == GROUNDED_DRAFT_SYSTEM
    prompt = messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "[billing] a duplicate charge is reversed" in prompt
    assert update["notes"] == ["drafted a grounded reply"]


@patch("scoutbot.core._client")
def test_draft_without_passages_stays_ungrounded(mock_client):
    """The honest fallback: no passages means the Week 8 draft, ungrounded system prompt and all.

    `initial_state` starts `retrieved` empty, so a draft node run before any retrieval behaves exactly
    as it did last week - which is what keeps every node callable in isolation.
    """
    from scoutbot.core import DRAFT_SYSTEM

    messages = _wire(mock_client)
    state = initial_state("I was charged twice.", "1001", "T-plain-draft")
    state["triage"] = VALID_TRIAGE

    update = draft_reply_node(state)

    assert messages.stream.call_args.kwargs["system"] == DRAFT_SYSTEM
    assert update["notes"] == ["drafted a reply"]


# --- Agentic retrieval: formulate, critique, and the re-query loop (Day 3) ------------------
# Day 2 retrieved once, on the raw ticket text. Day 3 wraps that single step in a loop the agent
# drives: it decides *what* to search for, judges what came back, and rewords and tries again when
# the result is weak. These cases test the three new plain functions in isolation, then the loop end
# to end - the reword-then-succeed path and the give-up-after-a-bound path - all offline.


def _scripted_formulate(*queries):
    """A fake `formulate_query` that returns a scripted query per attempt.

    The node passes `tried_queries`, whose length is how many searches have already happened, so
    `len(tried_queries)` indexes straight into the script. The last entry repeats if the loop runs
    longer than the script, which is what the give-up test relies on.
    """

    def fn(ticket_text, tried_queries=(), weak_passages=""):
        return queries[min(len(tried_queries), len(queries) - 1)]

    return fn


def _billing_only_kb() -> KnowledgeBase:
    """One passage, on the billing axis, so a non-billing query scores a clean 0.0 rather than a tie.

    The four-passage `_fake_kb` ties every off-axis query at 0.5, which is *at* the confidence floor,
    not under it - useless for testing a miss. A single one-hot passage makes an off-axis query
    genuinely orthogonal, so `shipping`-flavoured text against it scores 0.0 and the critique fails.
    """
    kb = KnowledgeBase(keyword_embedder)
    kb.index([Chunk("billing", 0, "a duplicate charge is reversed within two days")])
    return kb


def test_formulate_query_node_opens_with_the_ticket_and_records_it():
    """First pass: `tried_queries` is empty, so the node asks for an opening query and records it.

    A plain function from state to a partial update, like every other node. The captured call proves
    the node hands the raw ticket and *no* prior queries to `formulate`, and the return proves it
    seeds both `search_query` (last-write) and `tried_queries` (the reducer's first element).
    """
    seen = {}

    def spy(ticket_text, tried_queries=(), weak_passages=""):
        seen["ticket"] = ticket_text
        seen["tried"] = list(tried_queries)
        seen["weak"] = weak_passages
        return "duplicate charge reversal"

    state = initial_state("I was charged twice.", "1001", "T-formulate")

    update = formulate_query_node(state, formulate=spy)

    assert seen == {"ticket": "I was charged twice.", "tried": [], "weak": ""}
    assert update["search_query"] == "duplicate charge reversal"
    assert update["tried_queries"] == ["duplicate charge reversal"]
    assert update["notes"] == ["search query: 'duplicate charge reversal'"]


def test_formulate_query_node_rewords_using_what_already_failed():
    """Second pass: the node hands `formulate` the tried queries and the weak passages, and says so.

    This is the whole difference between a retry and a *reword*: the model is told what it already
    tried and what those tries returned, so it can move rather than repeat. The note switches to the
    "reworded (try N)" form, with N counting from the queries already in state.
    """
    seen = {}

    def spy(ticket_text, tried_queries=(), weak_passages=""):
        seen["tried"] = list(tried_queries)
        seen["weak"] = weak_passages
        return "second attempt query"

    state = initial_state("I was charged twice.", "1001", "T-reword")
    state["tried_queries"] = ["first attempt query"]
    state["retrieved"] = [
        {"source": "shipping", "ordinal": 0, "text": "shipping is free over fifty euros", "score": 0.1}
    ]

    update = formulate_query_node(state, formulate=spy)

    assert seen["tried"] == ["first attempt query"]
    assert "[shipping] shipping is free over fifty euros" in seen["weak"]
    assert update["search_query"] == "second attempt query"
    assert update["tried_queries"] == ["second attempt query"]
    assert update["notes"] == ["reworded the search (try 2): 'second attempt query'"]


def test_critique_passes_a_confident_retrieval():
    """A best score at or above the floor is `retrieval_ok=True`, and the note names the score."""
    state = initial_state("I was charged twice.", "1001", "T-crit-ok")
    state["tried_queries"] = ["charged twice"]
    state["retrieved"] = [{"source": "billing", "ordinal": 0, "text": "...", "score": 0.9}]

    update = critique_retrieval_node(state)

    assert update["retrieval_ok"] is True
    assert update["notes"] == ["critique: retrieval is sufficient (best 0.90)"]


def test_critique_flags_a_weak_retrieval_that_still_has_tries_left():
    """Below the floor with attempts to spare: not ok, and the note says it will reword."""
    state = initial_state("I was charged twice.", "1001", "T-crit-weak")
    state["tried_queries"] = ["charged twice"]
    state["retrieved"] = [{"source": "shipping", "ordinal": 0, "text": "...", "score": 0.1}]

    update = critique_retrieval_node(state)

    assert update["retrieval_ok"] is False
    assert update["notes"] == ["critique: weak (best 0.10); rewording and trying again"]


def test_critique_gives_up_once_the_attempt_bound_is_reached():
    """Weak *and* out of tries: still not ok, but the note announces a decline rather than a reword.

    The router reads the same two facts and sends this to the draft, where the grounded prompt turns a
    thin retrieval into "a teammate will follow up" instead of a guess. The critique's job is only to
    label it honestly.
    """
    state = initial_state("I was charged twice.", "1001", "T-crit-giveup")
    state["tried_queries"] = ["q"] * MAX_RETRIEVAL_ATTEMPTS
    state["retrieved"] = [{"source": "shipping", "ordinal": 0, "text": "...", "score": 0.1}]

    update = critique_retrieval_node(state)

    assert update["retrieval_ok"] is False
    assert update["notes"] == [
        f"critique: still weak after {MAX_RETRIEVAL_ATTEMPTS} tries (best 0.10); drafting a decline"
    ]


def test_route_after_critique_covers_its_three_exits():
    """The loop's control flow, tested with hand-made dicts and no graph.

    Draft when the critique passed; draft when it failed but the attempt bound is spent; reword only
    when there is both a reason to (weak) and room to (tries left).
    """
    assert route_after_critique({"retrieval_ok": True, "tried_queries": ["a"]}) == "draft_reply"
    assert (
        route_after_critique({"retrieval_ok": False, "tried_queries": ["a"]}) == "reformulate"
    )
    exhausted = {"retrieval_ok": False, "tried_queries": ["q"] * MAX_RETRIEVAL_ATTEMPTS}
    assert route_after_critique(exhausted) == "draft_reply"


@patch("scoutbot.core._client")
def test_a_weak_first_query_rewords_and_a_second_search_succeeds(mock_client):
    """The happy path of the loop, end to end: one miss, one reword, then a hit.

    The scripted `formulate` first returns a shipping-flavoured query, which scores 0.0 against the
    billing-only store and fails the critique; on the loop back it returns a billing query, which
    scores 1.0 and passes. The run then drafts grounded and pauses, so `tried_queries` is the record
    of both attempts and the notes carry the miss, the reword, and the passing critique in order.
    """
    _wire(mock_client)
    graph = build_ticket_graph(
        kb=_billing_only_kb(),
        formulate=_scripted_formulate("where is my delivery", "why was I charged twice"),
    )

    final = graph.invoke(
        initial_state("I was charged twice.", "1001", "T-loop"), thread_config("T-loop")
    )

    assert final["tried_queries"] == ["where is my delivery", "why was I charged twice"]
    assert final["search_query"] == "why was I charged twice"
    assert final["retrieval_ok"] is True
    assert final["draft_reply"] == DRAFT_TEXT
    assert final["notes"] == [
        "looked up 1001: found",
        RECALL_NOTE_NONE_1001,
        "triaged as billing/high",
        ROUTE_NOTE_ITERATIVE,
        "search query: 'where is my delivery'",
        "retrieved 1 passages but the best only scored 0.00 (under 0.5, so likely not covered)",
        "critique: weak (best 0.00); rewording and trying again",
        "reworded the search (try 2): 'why was I charged twice'",
        RETRIEVE_NOTE_BILLING.replace("3 passages", "1 passages"),
        CRITIQUE_NOTE_OK,
        "drafted a grounded reply",
        POLICY_NOTE_HIGH,
    ]


@patch("scoutbot.core._client")
def test_the_loop_is_bounded_and_drafts_a_decline_after_max_attempts(mock_client):
    """The safety property: an agent that can reword must not reword forever.

    Every scripted query is off-axis, so every search misses and every critique fails. The bound is
    `MAX_RETRIEVAL_ATTEMPTS`, so the loop runs exactly that many searches and then drafts anyway. The
    proof is `tried_queries` being exactly that length and the last critique announcing a decline -
    the run finishes rather than spinning.
    """
    _wire(mock_client)
    graph = build_ticket_graph(
        kb=_billing_only_kb(),
        formulate=_scripted_formulate("where is my delivery"),
    )

    final = graph.invoke(
        initial_state("I was charged twice.", "1001", "T-bound"), thread_config("T-bound")
    )

    assert len(final["tried_queries"]) == MAX_RETRIEVAL_ATTEMPTS
    assert final["retrieval_ok"] is False
    assert final["draft_reply"] == DRAFT_TEXT
    assert final["notes"].count("critique: weak (best 0.00); rewording and trying again") == (
        MAX_RETRIEVAL_ATTEMPTS - 1
    )
    # The run pauses at `escalate` (billing/high), so the give-up critique and the grounded draft are
    # the last two things the loop wrote before the policy note.
    give_up = f"critique: still weak after {MAX_RETRIEVAL_ATTEMPTS} tries (best 0.00); drafting a decline"
    assert give_up in final["notes"]
    assert final["notes"].index(give_up) < final["notes"].index("drafted a grounded reply")


# --- Adaptive routing: classify the query, then spend retrieval to match (Day 4) -----------
# Day 3 ran the full loop on every ticket. Day 4 routes first: a `direct` ticket skips retrieval
# entirely, a `retrieve` ticket searches once and does not loop, and an `iterative` ticket gets the
# whole Day 3 loop. The classifier is a model call (injected, like `formulate`); the router that
# reads its answer is a plain function. These cases test both in isolation, then each route end to end.


def test_classify_query_node_records_the_route():
    """The node calls the injected classifier and writes its answer, with a matching note.

    A plain function from state to a partial update, like every other node. The captured call proves
    it hands the classifier just the ticket text, and the three returns prove it stores whatever
    strategy came back.
    """
    for route, expected_note in [
        (QueryRoute.direct.value, "routed to a direct reply (no retrieval needed)"),
        (QueryRoute.retrieve.value, "routed to a single retrieval"),
        (QueryRoute.iterative.value, "routed to iterative retrieval"),
    ]:
        seen = {}

        def spy(ticket_text, _route=route):
            seen["ticket"] = ticket_text
            return _route

        state = initial_state("Thanks, that's all!", "1001", "T-classify")

        update = classify_query_node(state, classify=spy)

        assert seen["ticket"] == "Thanks, that's all!"
        assert update["route"] == route
        assert update["notes"] == [expected_note]


def test_route_query_covers_its_three_exits():
    """The adaptive fork, tested with hand-made dicts and no graph.

    `direct` and `retrieve` return themselves; `iterative` does too, and so does anything unexpected,
    because the safe default when routing is unclear is to search harder, never to skip the search.
    """
    assert route_query({"route": QueryRoute.direct.value}) == "direct"
    assert route_query({"route": QueryRoute.retrieve.value}) == "retrieve"
    assert route_query({"route": QueryRoute.iterative.value}) == "iterative"
    # A missing or unrecognised route falls back to the thorough path, not the cheap one.
    assert route_query({}) == "iterative"
    assert route_query({"route": "nonsense"}) == "iterative"


def test_route_after_critique_lets_a_single_retrieval_skip_the_reword():
    """Day 4's one change to the loop's exit: a single-shot `retrieve` never rewords.

    The score is weak and there are tries to spare, which on the `iterative` route means reformulate.
    On the `retrieve` route the same weak result drafts anyway, because one search is the strategy.
    """
    weak = {"retrieval_ok": False, "tried_queries": ["a"]}
    assert route_after_critique({**weak, "route": QueryRoute.iterative.value}) == "reformulate"
    assert route_after_critique({**weak, "route": QueryRoute.retrieve.value}) == "draft_reply"


@patch("scoutbot.core._client")
def test_a_direct_ticket_skips_retrieval_entirely(mock_client):
    """The whole point of the `direct` route: no search, no citation, no retrieval model calls.

    A "thanks, that's all" ticket is routed `direct`, so the run goes straight from the router to the
    draft. `search_query` and `retrieved` stay empty, the draft is ungrounded (the Week 8 note), and
    the streamed node order shows the loop's three nodes were never entered.
    """
    _wire(mock_client, LOW_TRIAGE)
    graph = build_ticket_graph(classify=lambda ticket_text: QueryRoute.direct.value)

    names = []
    for chunk in graph.stream(
        initial_state("Thanks, that's all I needed!", "1001", "T-direct"),
        thread_config("T-direct"),
        stream_mode="updates",
    ):
        names.extend(chunk)
    final = graph.get_state(thread_config("T-direct")).values

    assert "formulate_query" not in names
    assert "retrieve_knowledge" not in names
    assert "critique_retrieval" not in names
    assert final["route"] == "direct"
    assert final["search_query"] == ""
    assert final["tried_queries"] == []
    assert final["retrieved"] == []
    assert "routed to a direct reply (no retrieval needed)" in final["notes"]
    assert "drafted a reply" in final["notes"]
    assert "drafted a grounded reply" not in final["notes"]


@patch("scoutbot.core._client")
def test_a_single_retrieval_ticket_searches_once_and_does_not_loop(mock_client):
    """The `retrieve` route: one search, and no reword even when it comes back weak.

    The scripted `formulate` returns a shipping query that scores 0.0 against the billing-only store,
    which on the `iterative` route would trigger a reword. Because this ticket is routed `retrieve`,
    the critique labels it weak-but-drafting-anyway and the run drafts after exactly one attempt.
    """
    _wire(mock_client)
    graph = build_ticket_graph(
        kb=_billing_only_kb(),
        classify=lambda ticket_text: QueryRoute.retrieve.value,
        formulate=_scripted_formulate("where is my delivery", "should never be used"),
    )

    final = graph.invoke(
        initial_state("I was charged twice.", "1001", "T-single"), thread_config("T-single")
    )

    assert final["route"] == "retrieve"
    assert final["tried_queries"] == ["where is my delivery"]
    assert final["retrieval_ok"] is False
    assert "critique: weak (best 0.00); single-retrieval route, drafting anyway" in final["notes"]
    assert not any("reworded" in note for note in final["notes"])


# --- Day 5: recalling and writing memory ---------------------------------------------------
# The store's own behaviour is tested in tests/test_memory.py. These cases are about the two nodes
# and their place in the graph: that recall writes what the store returns into `recalled`, that write
# remembers once, and - the day's whole point - that a memory written by one ticket reaches the draft
# prompt of the next ticket from the same customer.
from scoutbot.graph import recall_memory_node, write_memory_node  # noqa: E402


def test_recall_memory_node_writes_what_the_store_returns_into_state():
    """A node, called as a plain function with an injected store: it recalls this customer's relevant
    past tickets and records them, both in `recalled` and as a note."""
    store = MemoryStore(keyword_embedder)
    store.write("1001", "T-old", "my refund never arrived")
    state = initial_state("Where is my refund?", "1001", "T-new")

    update = recall_memory_node(state, store=store)

    assert [m["ticket_id"] for m in update["recalled"]] == ["T-old"]
    assert update["notes"] == ["recalled 1 past ticket(s) for 1001"]


def test_recall_memory_node_with_no_history_recalls_nothing():
    store = MemoryStore(keyword_embedder)
    update = recall_memory_node(initial_state("Hello", "1001", "T-1"), store=store)
    assert update["recalled"] == []
    assert update["notes"] == ["no past tickets on file for 1001"]


def test_write_memory_node_remembers_once_then_declines():
    """The idempotency guard, at the node: the first write stores the ticket and says so; a second
    call for the same ticket writes nothing, the send-ledger's 'act once' applied to remembering."""
    store = MemoryStore(keyword_embedder)
    state = initial_state("I was charged twice.", "1001", "T-w")
    state["triage"] = VALID_TRIAGE
    state["resolution"] = {"path": "auto_approved"}

    first = write_memory_node(state, store=store)
    assert first["notes"] == ["remembered this ticket for 1001"]
    assert store.count("1001") == 1

    second = write_memory_node(state, store=store)
    assert second["notes"] == ["already remembered T-w, nothing new written"]
    assert store.count("1001") == 1


@patch("scoutbot.core._client")
def test_a_returning_customer_brings_last_ticket_into_the_next_draft(mock_client):
    """The whole week, in one assertion: a memory written when one ticket finished is recalled by the
    next ticket from the same customer and reaches the draft prompt as background.

    Two full runs share one injected store. The first ticket auto-approves and finishes, so
    `write_memory` records it. The second ticket, from the same customer, recalls it - it lands in
    `recalled` and, because `draft_reply` passes recalled memory to `stream_reply`, the first ticket's
    text is in the prompt the second draft is written from. The `messages.stream` mock captures the
    last call, which is that second draft.
    """
    _wire(mock_client, LOW_TRIAGE)
    store = MemoryStore(keyword_embedder)
    graph = build_ticket_graph(memory=store)

    graph.invoke(
        initial_state("My refund never arrived.", "1001", "T-first"), thread_config("run-first")
    )
    assert store.count("1001") == 1

    second = graph.invoke(
        initial_state("Any update on my refund?", "1001", "T-second"), thread_config("run-second")
    )

    assert [m["ticket_id"] for m in second["recalled"]] == ["T-first"]
    assert "recalled 1 past ticket(s) for 1001" in second["notes"]
    draft_prompt = mock_client.return_value.messages.stream.call_args.kwargs["messages"][0][
        "content"
    ]
    assert "My refund never arrived." in draft_prompt
    # Memory is background, not a citation: it must not arrive dressed as a policy source.
    assert "(ticket T-first)" in draft_prompt


@patch("scoutbot.core._client")
def test_a_first_time_customer_drafts_with_no_memory_block(mock_client):
    """The other side: a customer with nothing on file recalls an empty list, and the draft prompt
    carries no memory block at all - `direct`/grounded behaviour is byte-for-byte Day 4's when there
    is nothing to recall."""
    _wire(mock_client, LOW_TRIAGE)
    store = MemoryStore(keyword_embedder)
    graph = build_ticket_graph(memory=store)

    final = graph.invoke(
        initial_state("How do I export a CSV?", "1001", "T-fresh"), thread_config("run-fresh")
    )

    assert final["recalled"] == []
    assert "no past tickets on file for 1001" in final["notes"]
    draft_prompt = mock_client.return_value.messages.stream.call_args.kwargs["messages"][0][
        "content"
    ]
    assert "already know about this customer" not in draft_prompt


# --- Pausing for a human, and resuming -----------------------------------------------------


@patch("scoutbot.core._client")
def test_the_pause_payload_carries_what_a_reviewer_needs(mock_client):
    """A payload of just an ID would technically pause. It would also be useless.

    New today: it names the approver the policy requires and the amount at stake, so the person
    reading it can tell whether it is theirs to answer.
    """
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-payload")

    final = graph.invoke(
        initial_state("I was charged twice.", "1001", "T-payload", refund_amount=900.0), config
    )
    payload = final["__interrupt__"][0].value

    assert payload["ticket_id"] == "T-payload"
    assert payload["draft_reply"] == DRAFT_TEXT
    assert payload["approver_required"] == "billing_manager"
    assert payload["amount"] == 900.0
    assert "900.00" in payload["why"]
    assert "pro plan" in payload["account"]


@patch("scoutbot.core._client")
def test_the_resume_value_is_what_the_interrupt_call_returns(mock_client):
    """`Command(resume=value)` hands `value` straight back into the node, unvalidated."""
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-resume")

    graph.invoke(initial_state("I was charged twice.", "1001", "T-resume"), config)
    final = graph.invoke(Command(resume={"approved": True, "by": "priya", "role": "support_lead"}), config)

    assert final["resolution"]["approved"] is True
    assert final["resolution"]["reviewed_by"] == "priya"
    # ..., "priya approved the draft", <send note>, <write_memory note>.
    assert final["notes"][-3] == "priya approved the draft"
    assert final["notes"][-1] == WRITE_NOTE_1001
    assert graph.get_state(config).next == ()


@patch("scoutbot.core._client")
def test_a_rejection_finishes_the_run_and_sends_nothing(mock_client):
    """The point of asking is that the answer can be no, and no is not an error.

    A rejection still runs `send_reply`, because both arms of the branch go there. The node reads
    the resolution and sends nothing, which is why the guard lives in the node rather than in the
    graph's shape.
    """
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-reject")

    graph.invoke(initial_state("I was charged twice.", "1001", "T-reject"), config)
    final = graph.invoke(Command(resume={"approved": False, "by": "dana", "role": "billing_manager"}), config)

    assert final["resolution"]["approved"] is False
    # `write_memory` runs after the send guard, so the "nothing sent" note is now second-to-last.
    assert final["notes"][-2] == "nothing sent: not approved"
    assert final["notes"][-1] == WRITE_NOTE_1001


@patch("scoutbot.core._client")
def test_an_unauthorised_approver_cannot_approve_and_nothing_is_sent(mock_client):
    """The first topic's teeth. `approver_required` in the payload is advisory; the check is not.

    Priya is a support lead. A nine-hundred-euro refund requires a billing manager, and nothing in
    `Command(resume=...)` stops her claiming otherwise, so `escalate_node` has to check. An
    unauthorised approval is recorded as a non-approval with a reason rather than raising.
    """
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-unauth")

    graph.invoke(
        initial_state("I want a refund.", "1001", "T-unauth", refund_amount=900.0), config
    )
    final = graph.invoke(
        Command(resume={"approved": True, "by": "priya", "role": "support_lead"}), config
    )

    assert final["resolution"]["approved"] is False
    assert final["resolution"]["authorised"] is False
    assert final["resolution"]["approver_required"] == "billing_manager"
    assert final["notes"][-3] == "priya (support_lead) may not approve this: billing_manager required"
    assert final["notes"][-2] == "nothing sent: not authorised"
    assert final["notes"][-1] == WRITE_NOTE_1001


@patch("scoutbot.core._client")
def test_a_billing_manager_can_approve_what_a_lead_cannot(mock_client):
    """The other side of the same rule, so the test suite says what is allowed as well as what is
    not: a billing manager outranks the requirement and the reply goes out."""
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-auth")

    graph.invoke(
        initial_state("I want a refund.", "1001", "T-auth", refund_amount=900.0), config
    )
    final = graph.invoke(
        Command(resume={"approved": True, "by": "dana", "role": "billing_manager"}), config
    )

    assert final["resolution"]["approved"] is True
    assert final["resolution"]["authorised"] is True
    assert final["notes"][-2] == "reply sent to the customer (ledger key T-auth:send_reply)"
    assert final["notes"][-1] == WRITE_NOTE_1001


@patch("scoutbot.core._client")
def test_a_bare_boolean_resume_value_also_works(mock_client):
    """Because `Command(resume=True)` is the form every tutorial uses, and LangGraph does not
    validate the value on its way into the node.

    Note the consequence, which is worth showing rather than hiding: a bare `True` carries no
    reviewer, so it cannot be authorised for anything, and this ticket's zero amount means only a
    support lead was needed. It still fails the check, and the run records why.
    """
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-bare")

    graph.invoke(initial_state("I was charged twice.", "1001", "T-bare"), config)
    final = graph.invoke(Command(resume=True), config)

    assert final["resolution"]["reviewed_by"] == "unknown"
    assert final["resolution"]["authorised"] is False


@patch("scoutbot.core._client")
def test_resuming_re_runs_the_paused_node_but_not_the_finished_ones(mock_client):
    """The asymmetry today's second topic is built on.

    Both model calls happened before the pause and neither happens again: their results come out
    of the checkpoint. The pausing node, though, is entered a second time and runs from its first
    line, which is why nothing expensive belongs above an `interrupt()`.
    """
    messages = _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-rerun")

    graph.invoke(initial_state("I was charged twice.", "1001", "T-rerun"), config)
    assert messages.create.call_count == 1
    assert messages.stream.call_count == 1

    graph.invoke(Command(resume={"approved": True, "by": "priya", "role": "support_lead"}), config)

    # Neither model call was repeated.
    assert messages.create.call_count == 1
    assert messages.stream.call_count == 1
    # And the notes prove the earlier nodes' work was reused rather than redone.
    assert graph.get_state(config).values["notes"].count("drafted a grounded reply") == 1


@patch("scoutbot.core._client")
def test_the_pausing_node_runs_its_own_code_again_on_resume(mock_client):
    """Same asymmetry, from the other side, and asserted directly rather than inferred.

    A counter wrapped around the node counts entries into it, not runs of the graph: one when the
    run pauses, a second when it resumes. This is the fact that makes the ledger necessary, so it
    is worth having asserted somewhere permanent.
    """
    _wire(mock_client)
    entries = []
    # Captured before the patch goes in, or the wrapper would call itself.
    real_escalate = graph_module.escalate_node

    def counting_escalate(state):
        entries.append(state["ticket_id"])
        return real_escalate(state)

    with patch("scoutbot.graph.escalate_node", counting_escalate):
        graph = build_ticket_graph()
        config = thread_config("T-count")
        graph.invoke(initial_state("I was charged twice.", "1001", "T-count"), config)
        assert entries == ["T-count"]

        graph.invoke(Command(resume={"approved": True, "by": "priya", "role": "support_lead"}), config)

    assert entries == ["T-count", "T-count"]


@patch("scoutbot.core._client")
def test_without_a_checkpointer_a_pause_fails_late_rather_than_loudly(mock_client):
    """The trap, and the reason `build_ticket_graph()` no longer compiles without a checkpointer.

    The docs list a checkpointer as a requirement for interrupts, which reads as though the
    absence of one would raise. It does not. The run appears to pause, `invoke()` returns an
    `__interrupt__` like normal, the node's own return value never materialises, and the failure
    surfaces only when someone tries to continue.
    """
    _wire(mock_client)
    graph = ticket_graph_builder().compile()

    final = graph.invoke(initial_state("I was charged twice.", "1001", "T-nocp"))

    assert "__interrupt__" in final
    assert final["resolution"] == {}

    with pytest.raises(RuntimeError, match="without checkpointer"):
        graph.invoke(Command(resume=True))


@patch("scoutbot.core._client")
def test_build_ticket_graph_defaults_to_an_in_memory_checkpointer(mock_client):
    """`None` used to mean "no memory". Today it means "memory for as long as this process"."""
    _wire(mock_client)
    graph = build_ticket_graph()
    config = thread_config("T-default")

    graph.invoke(initial_state("I was charged twice.", "1001", "T-default"), config)

    # Nothing raises, and the paused run is genuinely retrievable.
    assert graph.get_state(config).next == ("escalate",)


# --- Sending exactly once ------------------------------------------------------------------
# The ledger's own behaviour is tested in tests/test_notify.py. These cases are about the node:
# that it respects the resolution, that a retry cannot make it send twice, and that a graph
# without a durable ledger is a graph whose guarantee ends with the process.


def test_send_reply_node_is_an_ordinary_function_with_its_own_ledger():
    """Same property as every other node in this package: callable with a hand-made dict."""
    ledger = Ledger.in_memory()
    state = initial_state("I was charged twice.", "1001", "T-plain-send")
    state["draft_reply"] = DRAFT_TEXT
    state["resolution"] = {"approved": True, "authorised": True}
    sent = []

    with patch("scoutbot.notify.print", create=True):
        update = send_reply_node(state, ledger=ledger)
    assert "reply sent to the customer" in update["notes"][0]

    # Called a second time with the same ledger, it declines rather than sending again.
    again = send_reply_node(state, ledger=ledger)
    assert again["notes"] == ["reply already sent for T-plain-send, so this attempt sent nothing"]
    assert sent == []


@patch("scoutbot.core._client")
def test_a_retry_after_a_successful_send_does_not_send_twice(mock_client):
    """The day's central guarantee, end to end, through a real retry.

    `fail_after_send=2` makes the gateway accept the mail and then drop the connection twice, so
    LangGraph's `RetryPolicy` runs `send_reply` three times over. Exactly one email leaves, because
    the ledger row written by the first attempt is what the second and third attempts find.

    Where the failure sits is the whole point and was verified before this was written: above the
    send, a retry never reaches the send and this test would pass with no ledger at all.
    """
    _wire(mock_client, LOW_TRIAGE)
    ledger = Ledger.in_memory()
    transport = []
    graph = build_ticket_graph(ledger=ledger, fail_after_send=2)

    with patch("scoutbot.notify.print", create=True):
        final = graph.invoke(
            initial_state("How do I export a CSV?", "1001", "T-retry"), thread_config("T-retry")
        )

    assert final["resolution"]["approved"] is True
    assert len(ledger.entries()) == 1
    assert ledger.entries()[0][0] == "T-retry:send_reply"
    assert transport == []


@patch("scoutbot.core._client")
def test_the_same_ticket_run_twice_only_ever_sends_one_email(mock_client):
    """A different route to the same duplicate: two whole runs of the same ticket.

    Two `thread_id`s, so LangGraph considers them unrelated runs and there is no checkpoint to
    dedupe against. The ledger is keyed on the *ticket*, not the run, which is what makes this the
    right question to ask of it.
    """
    _wire(mock_client, LOW_TRIAGE)
    ledger = Ledger.in_memory()
    graph = build_ticket_graph(ledger=ledger)

    with patch("scoutbot.notify.print", create=True):
        graph.invoke(
            initial_state("How do I export a CSV?", "1001", "T-twice"), thread_config("run-a")
        )
        second = graph.invoke(
            initial_state("How do I export a CSV?", "1001", "T-twice"), thread_config("run-b")
        )

    # The send note is second-to-last now; `write_memory` closes the run, and because the first run
    # already remembered T-twice for this customer, the second run's write is the idempotent no-op -
    # the same "remember once" the ledger enforces for the send.
    assert second["notes"][-2] == "reply already sent for T-twice, so this attempt sent nothing"
    assert second["notes"][-1] == "already remembered T-twice, nothing new written"
    assert len(ledger.entries()) == 1


@patch("scoutbot.core._client")
def test_a_file_backed_ledger_survives_into_a_second_graph(mock_client, tmp_path):
    """The durability claim, applied to side effects rather than to progress.

    Two graphs, two `Ledger.at()` connections to one file, no shared memory: the second refuses to
    send what the first already sent. `tests/test_resume_across_processes.py` is what proves the
    same thing across two real OS processes.
    """
    _wire(mock_client, LOW_TRIAGE)
    db = tmp_path / "ledger.db"

    with patch("scoutbot.notify.print", create=True):
        first = build_ticket_graph(ledger=Ledger.at(db))
        first.invoke(
            initial_state("How do I export a CSV?", "1001", "T-file"), thread_config("run-1")
        )

        second = build_ticket_graph(ledger=Ledger.at(db))
        final = second.invoke(
            initial_state("How do I export a CSV?", "1001", "T-file"), thread_config("run-2")
        )

    assert final["notes"][-2] == "reply already sent for T-file, so this attempt sent nothing"
    assert final["notes"][-1] == "already remembered T-file, nothing new written"
    assert len(Ledger.at(db).entries()) == 1


# --- Checkpointing -------------------------------------------------------------------------


@patch("scoutbot.core._client")
def test_in_memory_checkpointer_keeps_the_finished_run_on_its_thread(mock_client):
    """A ticket the policy clears, because that is the branch that finishes in one call."""
    _wire(mock_client, LOW_TRIAGE)
    graph = build_ticket_graph(InMemorySaver())
    config = thread_config("T-4471")

    graph.invoke(initial_state("How do I export a CSV?", "1001", "T-4471"), config)
    snapshot = graph.get_state(config)

    assert snapshot.values["triage"] == LOW_TRIAGE
    assert snapshot.values["resolution"]["path"] == "auto_approved"
    # Nothing left to run, so this run is complete rather than merely saved.
    assert snapshot.next == ()


@patch("scoutbot.core._client")
def test_get_state_names_the_node_that_still_has_to_run(mock_client, tmp_path):
    _wire(mock_client)
    config = thread_config("T-4471")

    with patch("scoutbot.graph.escalate_node", _boom):
        graph = build_ticket_graph(sqlite_checkpointer(tmp_path / "checkpoints.db"))
        with pytest.raises(RuntimeError):
            graph.invoke(
                initial_state("I was charged twice.", "1001", "T-4471"),
                config,
                durability="sync",
            )

    snapshot = graph.get_state(config)
    assert snapshot.next == ("escalate",)
    assert snapshot.values["triage"] == VALID_TRIAGE
    assert snapshot.values["resolution"] == {}


@patch("scoutbot.core._client")
def test_crash_then_resume_does_not_re_run_the_model_calls(mock_client, tmp_path):
    """Day 2's central claim, still true with today's extra nodes in the graph.

    The resume happens through a second `sqlite_checkpointer()` call, so it reads the file over a
    fresh connection and shares no in-memory state with the graph that crashed.
    `tests/test_resume_across_processes.py` is what proves the same thing across two real OS
    processes, which is the claim the slides actually make.
    """
    messages = _wire(mock_client)
    db = tmp_path / "checkpoints.db"
    config = thread_config("T-4471")
    start = initial_state("I was charged twice.", "1001", "T-4471")

    with patch("scoutbot.graph.escalate_node", _boom):
        crashed = build_ticket_graph(sqlite_checkpointer(db))
        with pytest.raises(RuntimeError):
            crashed.invoke(start, config, durability="sync")

    assert messages.create.call_count == 1
    assert messages.stream.call_count == 1

    resumed = build_ticket_graph(sqlite_checkpointer(db), ledger=Ledger.at(db))
    recovered = resumed.invoke(None, config)

    assert recovered["triage"] == VALID_TRIAGE
    assert recovered["draft_reply"] == DRAFT_TEXT
    assert "__interrupt__" in recovered
    # The expensive nodes completed before the crash, so resuming reads their results.
    assert messages.create.call_count == 1
    assert messages.stream.call_count == 1

    with patch("scoutbot.notify.print", create=True):
        final = resumed.invoke(Command(resume={"approved": True, "by": "priya", "role": "support_lead"}), config)
    assert final["resolution"]["path"] == "escalated"
    assert final["notes"] == [
        "looked up 1001: found",
        RECALL_NOTE_NONE_1001,
        "triaged as billing/high",
        ROUTE_NOTE_ITERATIVE,
        QUERY_NOTE_BILLING,
        RETRIEVE_NOTE_BILLING,
        CRITIQUE_NOTE_OK,
        "drafted a grounded reply",
        POLICY_NOTE_HIGH,
        "priya approved the draft",
        "reply sent to the customer (ledger key T-4471:send_reply)",
        WRITE_NOTE_1001,
    ]


@patch("scoutbot.core._client")
def test_resuming_with_input_instead_of_a_command_re_runs_the_whole_graph(mock_client, tmp_path):
    """The teachable bug, and it does not fail loudly. Same shape as Day 2's version.

    Passing the initial state again rather than `Command(resume=...)` starts a fresh run from the
    entry node on top of the state already on the thread. Both model calls happen again, and
    because `notes` has a reducer the recovered notes are duplicated rather than replaced, so the
    damage is additive and easy to miss in output. Then the run reaches the same pause again.
    """
    messages = _wire(mock_client)
    db = tmp_path / "checkpoints.db"
    config = thread_config("T-4471")
    start = initial_state("I was charged twice.", "1001", "T-4471")
    graph = build_ticket_graph(sqlite_checkpointer(db))

    graph.invoke(start, config, durability="sync")
    assert graph.get_state(config).next == ("escalate",)

    graph.invoke(start, config, durability="sync")

    assert messages.create.call_count == 2
    assert messages.stream.call_count == 2
    snapshot = graph.get_state(config)
    assert snapshot.values["notes"].count("triaged as billing/high") == 2
    assert snapshot.values["resolution"] == {}
    # And it is still waiting, exactly where it was.
    assert snapshot.next == ("escalate",)


@patch("scoutbot.core._client")
def test_two_thread_ids_on_one_database_stay_independent(mock_client, tmp_path):
    """One checkpoint file holds many runs. `thread_id` is what keeps them apart, which is why
    reusing one by accident resumes into another ticket's history."""
    _wire(mock_client)
    graph = build_ticket_graph(sqlite_checkpointer(tmp_path / "checkpoints.db"))

    graph.invoke(initial_state("I was charged twice.", "1001", "T-1"), thread_config("T-1"))
    other = graph.get_state(thread_config("T-2"))

    assert other.values == {}
    assert graph.get_state(thread_config("T-1")).values["ticket_id"] == "T-1"
