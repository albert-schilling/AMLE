import pytest
from langgraph.checkpoint.memory import InMemorySaver

from ticket_classifier.batch import classify_all
from ticket_classifier.graph import build_workflow
from ticket_classifier.models import (
    EscalatedTicket,
    ResolvedTicket,
    TicketClassification,
)

CONFIG = {"configurable": {"thread_id": "T-1"}}


@pytest.fixture
def parse(mocker):
    """Mock the triage model call; returns the mock to count calls."""
    classification = TicketClassification(category="billing", priority="high")
    client = mocker.patch("ticket_classifier.triage_node.get_client").return_value
    client.messages.parse.return_value.content = [
        mocker.Mock(parsed_output=classification)
    ]
    mocker.patch("ticket_classifier.nodes.get_customer", return_value=None)
    mocker.patch("ticket_classifier.batch.log_action")
    return client.messages.parse


def test_high_priority_ticket_pauses_for_a_human(parse, make_ticket):
    workflow = build_workflow(InMemorySaver())

    batch = classify_all([make_ticket(id="T-1")], workflow=workflow)

    assert batch.paused == ["T-1"]
    assert batch.classified == []
    state = workflow.get_state(CONFIG)
    assert state.next == ("node_wait_for_human",)
    request = state.interrupts[0].value
    assert request["ticket"]["text"] == "Test ticket"
    assert request["classification"] == {"category": "billing", "priority": "high"}


def test_paused_run_without_answer_stays_paused(parse, make_ticket):
    workflow = build_workflow(InMemorySaver())
    ticket = make_ticket(id="T-1")
    classify_all([ticket], workflow=workflow)

    batch = classify_all([ticket], workflow=workflow)

    assert batch.paused == ["T-1"]
    assert parse.call_count == 1


def test_approved_answer_finishes_the_run_escalated(parse, make_ticket):
    workflow = build_workflow(InMemorySaver())
    ticket = make_ticket(id="T-1")
    classify_all([ticket], workflow=workflow)

    answer = {"approved": True, "note": "Dana takes it"}
    batch = classify_all([ticket], workflow=workflow, answers={"T-1": answer})

    assert batch.classified == [
        EscalatedTicket(
            ticket_id="T-1",
            category="billing",
            priority="high",
            escalation_reason="Dana takes it",
        )
    ]
    assert workflow.get_state(CONFIG).next == ()
    assert parse.call_count == 1  # triage did not run again


def test_declined_answer_finishes_the_run_resolved(parse, make_ticket):
    workflow = build_workflow(InMemorySaver())
    ticket = make_ticket(id="T-1")
    classify_all([ticket], workflow=workflow)

    answer = {"approved": False, "note": "Bot can answer this"}
    batch = classify_all([ticket], workflow=workflow, answers={"T-1": answer})

    assert batch.classified == [
        ResolvedTicket(ticket_id="T-1", category="billing", priority="high")
    ]


def test_crashed_run_continues_without_calling_the_model_again(parse, make_ticket):
    workflow = build_workflow(InMemorySaver())
    ticket = make_ticket(id="T-1")

    # First run stops right after triage, before the last node starts.
    for values in workflow.stream({"ticket": ticket}, CONFIG, stream_mode="values"):
        if values.get("classification"):
            break
    assert workflow.get_state(CONFIG).next == ("node_wait_for_human",)
    assert workflow.get_state(CONFIG).interrupts == ()

    batch = classify_all([ticket], workflow=workflow)

    assert batch.paused == ["T-1"]
    assert parse.call_count == 1
