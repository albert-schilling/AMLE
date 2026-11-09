"""These tests patch the Anthropic SDK boundary directly (`scoutbot.core._client`), so they run
offline - no real API key or network access needed, same pattern as every earlier day. The graph
itself needs no mocking: LangGraph runs entirely locally, and `look_up_customer` reads the
repo's own `mock_customers.json`.

What's worth testing on a day about state is not "does the model answer correctly" but the state
mechanics themselves: that a node's partial return gets merged rather than replacing everything,
that the reducer field accumulates while plain fields do not, and that the second node genuinely
sees what the first one wrote instead of being handed the ticket text directly.
"""
from types import SimpleNamespace
from unittest.mock import patch

from scoutbot.graph import (
    TicketState,
    build_ticket_graph,
    initial_state,
    look_up_customer_node,
    run_ticket_graph,
)

VALID_TRIAGE = {"category": "billing", "priority": "high", "suggested_owner": "billing-team"}


def _fake_response(input_dict: dict = None):
    """Mimics an Anthropic Message response carrying one tool_use block, same helper shape as
    tests/test_triage.py."""
    block = SimpleNamespace(
        type="tool_use", name="triage_ticket", input=input_dict or VALID_TRIAGE
    )
    return SimpleNamespace(content=[block])


@patch("scoutbot.core._client")
def test_graph_runs_both_nodes_and_fills_every_declared_field(mock_client):
    mock_client.return_value.messages.create.return_value = _fake_response()

    final = run_ticket_graph("I was charged twice.", customer_id="1001", ticket_id="T-3001")

    assert final["customer"]["found"] is True
    assert final["customer"]["plan"] == "pro"
    assert final["triage"] == VALID_TRIAGE
    # Inputs are carried through untouched - no node returned them, so nothing overwrote them.
    assert final["ticket_id"] == "T-3001"
    assert final["customer_id"] == "1001"


@patch("scoutbot.core._client")
def test_notes_accumulate_across_nodes_because_of_the_reducer(mock_client):
    """`notes` is `Annotated[list[str], operator.add]`, so the second node's list is appended to
    the first node's rather than replacing it. Without the reducer this would be length 1."""
    mock_client.return_value.messages.create.return_value = _fake_response()

    final = run_ticket_graph("I was charged twice.", customer_id="1001")

    assert len(final["notes"]) == 2
    assert final["notes"][0] == "looked up 1001: found"
    assert final["notes"][1] == "triaged as billing/high"


@patch("scoutbot.core._client")
def test_plain_field_is_replaced_not_merged(mock_client):
    """`customer` has no reducer, so the node's record replaces the empty dict it started as,
    instead of being merged into it."""
    mock_client.return_value.messages.create.return_value = _fake_response()
    start = initial_state("I was charged twice.", customer_id="1001")
    start["customer"] = {"stale": "should be gone"}

    final = build_ticket_graph().invoke(start)

    assert "stale" not in final["customer"]
    assert final["customer"]["customer_id"] == "1001"


@patch("scoutbot.core._client")
def test_second_node_reads_what_the_first_node_wrote(mock_client):
    """The triage node must build its prompt from state, not from the ticket text alone - the
    looked-up record has to reach the model, or shared state is decorative."""
    mock_client.return_value.messages.create.return_value = _fake_response()

    run_ticket_graph("I was charged twice.", customer_id="1001")

    prompt = mock_client.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "I was charged twice." in prompt
    assert "Customer record:" in prompt
    assert '"plan": "pro"' in prompt


@patch("scoutbot.core._client")
def test_streaming_yields_one_update_per_node_in_order(mock_client):
    """`stream_mode="updates"` is how the live lesson shows state changing: one chunk per node,
    keyed by node name, containing only that node's own fields."""
    mock_client.return_value.messages.create.return_value = _fake_response()
    graph = build_ticket_graph()

    chunks = list(
        graph.stream(initial_state("I was charged twice.", "1001"), stream_mode="updates")
    )

    assert [name for chunk in chunks for name in chunk] == [
        "look_up_customer",
        "triage_ticket",
    ]
    assert set(chunks[0]["look_up_customer"]) == {"customer", "notes"}
    assert set(chunks[1]["triage_ticket"]) == {"triage", "notes"}


@patch("scoutbot.core._client")
def test_unknown_customer_still_reaches_the_triage_node(mock_client):
    """There is no conditional edge yet - that's tomorrow. A missing customer record is written
    into state like any other result, and the graph carries straight on to triage."""
    mock_client.return_value.messages.create.return_value = _fake_response()

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
