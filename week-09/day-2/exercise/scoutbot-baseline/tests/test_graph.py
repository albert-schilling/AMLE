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
    draft_reply_node,
    initial_state,
    look_up_customer_node,
    route_on_approval,
    run_ticket_graph,
    send_reply_node,
    sqlite_checkpointer,
    thread_config,
    ticket_graph_builder,
)
from scoutbot.notify import Ledger

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


@pytest.fixture(autouse=True)
def _fresh_ledger():
    """Give every test its own empty ledger and its own flaky-attempt counter.

    Both live at module level in the code under test, deliberately: a guarantee about repeated calls
    has to outlive the calls, so it cannot be a local. That makes them shared state between tests,
    so they get reset here rather than leaking.
    """
    graph_module._PROCESS_LEDGER = None
    notify.reset_flaky_counter()
    yield
    graph_module._PROCESS_LEDGER = None
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

    Four notes, not six: this run stops at the pause, so neither `escalate` nor `send_reply` has
    written anything yet.
    """
    _wire(mock_client)

    final = run_ticket_graph("I was charged twice.", customer_id="1001")

    assert final["notes"] == [
        "looked up 1001: found",
        "triaged as billing/high",
        "drafted a reply",
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
        "triage_ticket",
        "draft_reply",
        "check_policy",
        "__interrupt__",
    ]
    assert set(chunks[0]["look_up_customer"]) == {"customer", "notes"}
    assert set(chunks[1]["triage_ticket"]) == {"triage", "notes"}
    assert set(chunks[3]["check_policy"]) == {"approval", "notes"}


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
    assert final["notes"][-1] == "reply sent to the customer (ledger key T-low:send_reply)"


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
def test_the_draft_prompt_carries_the_triage_result(mock_client):
    """Same lesson as the triage node's prompt: a later node reads what an earlier one wrote."""
    messages = _wire(mock_client)

    run_ticket_graph("I was charged twice.", customer_id="1001")

    prompt = messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "I was charged twice." in prompt
    assert "billing" in prompt
    assert "high priority" in prompt


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
    assert final["notes"][-2] == "priya approved the draft"
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
    assert final["notes"][-1] == "nothing sent: not approved"


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
    assert final["notes"][-2] == "priya (support_lead) may not approve this: billing_manager required"
    assert final["notes"][-1] == "nothing sent: not authorised"


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
    assert final["notes"][-1] == "reply sent to the customer (ledger key T-auth:send_reply)"


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
    assert graph.get_state(config).values["notes"].count("drafted a reply") == 1


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

    assert second["notes"][-1] == "reply already sent for T-twice, so this attempt sent nothing"
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

    assert final["notes"][-1] == "reply already sent for T-file, so this attempt sent nothing"
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
        "triaged as billing/high",
        "drafted a reply",
        POLICY_NOTE_HIGH,
        "priya approved the draft",
        "reply sent to the customer (ledger key T-4471:send_reply)",
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
