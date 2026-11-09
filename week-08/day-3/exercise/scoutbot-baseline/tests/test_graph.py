"""These tests patch the Anthropic SDK boundary directly (`scoutbot.core._client`), so they run
offline - no real API key or network access needed, same pattern as every earlier day. The graph
itself needs no mocking: LangGraph runs entirely locally, and `look_up_customer` reads the
repo's own `mock_customers.json`.

What's worth testing on a day about state is not "does the model answer correctly" but the state
mechanics themselves: that a node's partial return gets merged rather than replacing everything,
that the reducer field accumulates while plain fields do not, and that the second node genuinely
sees what the first one wrote instead of being handed the ticket text directly.

Day 2 adds two groups of cases. The router ones need no mocking at all, since a router is a plain
function of a hand-made state dict. The checkpointer ones use a real SQLite file in pytest's
`tmp_path` and open a *second* connection to it to resume, which is as close to "a different
process" as an in-process test can honestly get; `run_resume.py` is what demonstrates the real
thing across two shells.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from scoutbot.graph import (
    TicketState,
    build_ticket_graph,
    initial_state,
    look_up_customer_node,
    route_after_triage,
    run_ticket_graph,
    sqlite_checkpointer,
    thread_config,
)

VALID_TRIAGE = {"category": "billing", "priority": "high", "suggested_owner": "billing-team"}
LOW_TRIAGE = {"category": "technical", "priority": "low", "suggested_owner": "support-team"}


def _fake_response(input_dict: dict = None):
    """Mimics an Anthropic Message response carrying one tool_use block, same helper shape as
    tests/test_triage.py."""
    block = SimpleNamespace(
        type="tool_use", name="triage_ticket", input=input_dict or VALID_TRIAGE
    )
    return SimpleNamespace(content=[block])


def _boom(state):
    """Stands in for the box being restarted, once triage has already completed and been saved.

    A plain function rather than a `Mock`, because LangGraph inspects a node's signature to work
    out what to pass it.
    """
    raise RuntimeError("the box restarted")


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
    """`notes` is `Annotated[list[str], operator.add]`, so each node's list is appended to what is
    already there rather than replacing it. Without the reducer this would be length 1.

    Three notes now rather than Day 1's two: every run passes through a terminal node as well.
    """
    mock_client.return_value.messages.create.return_value = _fake_response()

    final = run_ticket_graph("I was charged twice.", customer_id="1001")

    assert len(final["notes"]) == 3
    assert final["notes"][0] == "looked up 1001: found"
    assert final["notes"][1] == "triaged as billing/high"
    assert final["notes"][2] == "escalated: high priority, needs a human"


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
        "escalate",
    ]
    assert set(chunks[0]["look_up_customer"]) == {"customer", "notes"}
    assert set(chunks[1]["triage_ticket"]) == {"triage", "notes"}


@patch("scoutbot.core._client")
def test_unknown_customer_still_reaches_the_triage_node(mock_client):
    """The branch is on the triage result, not on the lookup: a missing customer record is
    written into state like any other result, and the graph carries straight on to triage."""
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


# --- Conditional routing -------------------------------------------------------------------
# No mocking anywhere in this group. A router is a plain function of state, so both branches of
# the day's central decision are testable with a hand-made dict, no graph and no API key.


def test_router_sends_high_priority_to_escalate():
    state = initial_state("I want a refund.", customer_id="1001")
    state["triage"] = VALID_TRIAGE

    assert route_after_triage(state) == "escalate"


def test_router_sends_everything_else_to_auto_resolve():
    state = initial_state("How do I export a CSV?", customer_id="1001")

    for priority in ("low", "medium"):
        state["triage"] = {**LOW_TRIAGE, "priority": priority}
        assert route_after_triage(state) == "auto_resolve"


@patch("scoutbot.core._client")
def test_high_priority_ticket_ends_at_the_escalate_node(mock_client):
    mock_client.return_value.messages.create.return_value = _fake_response()

    final = run_ticket_graph("I was charged twice.", customer_id="1001")

    assert final["resolution"]["path"] == "escalated"
    assert final["resolution"]["awaiting_human"] is True
    assert final["notes"][-1] == "escalated: high priority, needs a human"


@patch("scoutbot.core._client")
def test_low_priority_ticket_ends_at_the_auto_resolve_node(mock_client):
    """The branch not taken leaves no trace at all: only one terminal node ever writes
    `resolution`, so its value doubles as a record of which way the run went."""
    mock_client.return_value.messages.create.return_value = _fake_response(LOW_TRIAGE)

    final = run_ticket_graph("How do I export a CSV?", customer_id="1001")

    assert final["resolution"]["path"] == "auto_resolved"
    assert final["resolution"]["awaiting_human"] is False
    assert "escalated: high priority, needs a human" not in final["notes"]


# --- Checkpointing -------------------------------------------------------------------------


@patch("scoutbot.core._client")
def test_without_a_checkpointer_nothing_is_remembered_between_runs(mock_client):
    """Day 1's graph, and the baseline the rest of this group is measured against. A thread ID
    buys nothing here, because there is nowhere to write it."""
    mock_client.return_value.messages.create.return_value = _fake_response()
    graph = build_ticket_graph()

    graph.invoke(initial_state("I was charged twice.", "1001", "T-1"), thread_config("T-1"))
    second = graph.invoke(initial_state("I was charged twice.", "1001", "T-1"), thread_config("T-1"))

    # Two independent runs: the second one's notes start from empty, not from the first one's.
    assert len(second["notes"]) == 3


@patch("scoutbot.core._client")
def test_in_memory_checkpointer_keeps_the_finished_run_on_its_thread(mock_client):
    mock_client.return_value.messages.create.return_value = _fake_response()
    graph = build_ticket_graph(InMemorySaver())
    config = thread_config("T-4471")

    graph.invoke(initial_state("I was charged twice.", "1001", "T-4471"), config)
    snapshot = graph.get_state(config)

    assert snapshot.values["triage"] == VALID_TRIAGE
    assert snapshot.values["resolution"]["path"] == "escalated"
    # Nothing left to run, so this run is complete rather than merely saved.
    assert snapshot.next == ()


@patch("scoutbot.core._client")
def test_get_state_names_the_node_that_still_has_to_run(mock_client, tmp_path):
    mock_client.return_value.messages.create.return_value = _fake_response()
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
def test_crash_then_resume_finishes_the_run_without_re_running_triage(mock_client, tmp_path):
    """The day's whole claim, in one test.

    The resume happens through a second `sqlite_checkpointer()` call, so it reads the file over a
    fresh connection and shares no in-memory state with the graph that crashed.
    `tests/test_resume_across_processes.py` is what proves the same thing across two real OS
    processes, which is the claim the slides actually make.

    `durability="sync"` is passed for the same reason the demo script passes it: it is what makes
    each step durable before the next one starts.
    """
    mock_client.return_value.messages.create.return_value = _fake_response()
    db = tmp_path / "checkpoints.db"
    config = thread_config("T-4471")
    start = initial_state("I was charged twice.", "1001", "T-4471")

    with patch("scoutbot.graph.escalate_node", _boom):
        crashed = build_ticket_graph(sqlite_checkpointer(db))
        with pytest.raises(RuntimeError):
            crashed.invoke(start, config, durability="sync")

    assert mock_client.return_value.messages.create.call_count == 1

    resumed = build_ticket_graph(sqlite_checkpointer(db))
    final = resumed.invoke(None, config)

    assert final["resolution"]["path"] == "escalated"
    assert final["triage"] == VALID_TRIAGE
    # The expensive node completed before the crash, so resuming reads its result rather than
    # paying for it again.
    assert mock_client.return_value.messages.create.call_count == 1
    assert final["notes"] == [
        "looked up 1001: found",
        "triaged as billing/high",
        "escalated: high priority, needs a human",
    ]


@patch("scoutbot.core._client")
def test_resuming_with_input_instead_of_none_re_runs_the_whole_graph(mock_client, tmp_path):
    """The day's teachable bug, and it does not fail loudly.

    Passing the initial state again rather than `None` starts a fresh run from the entry node on
    top of the state already on the thread. The model is called a second time, and because `notes`
    has a reducer, the recovered notes are duplicated rather than replaced, so the damage is
    additive and easy to miss in output.
    """
    mock_client.return_value.messages.create.return_value = _fake_response()
    db = tmp_path / "checkpoints.db"
    config = thread_config("T-4471")
    start = initial_state("I was charged twice.", "1001", "T-4471")

    with patch("scoutbot.graph.escalate_node", _boom):
        crashed = build_ticket_graph(sqlite_checkpointer(db))
        with pytest.raises(RuntimeError):
            crashed.invoke(start, config, durability="sync")

    resumed = build_ticket_graph(sqlite_checkpointer(db))
    final = resumed.invoke(start, config, durability="sync")

    assert mock_client.return_value.messages.create.call_count == 2
    assert final["notes"].count("triaged as billing/high") == 2


@patch("scoutbot.core._client")
def test_two_thread_ids_on_one_database_stay_independent(mock_client, tmp_path):
    """One checkpoint file holds many runs. `thread_id` is what keeps them apart, which is why
    reusing one by accident resumes into another ticket's history."""
    mock_client.return_value.messages.create.return_value = _fake_response()
    graph = build_ticket_graph(sqlite_checkpointer(tmp_path / "checkpoints.db"))

    graph.invoke(initial_state("I was charged twice.", "1001", "T-1"), thread_config("T-1"))
    other = graph.get_state(thread_config("T-2"))

    assert other.values == {}
    assert graph.get_state(thread_config("T-1")).values["ticket_id"] == "T-1"
