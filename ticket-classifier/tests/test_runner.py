"""The runner on the real graph and an in-memory checkpointer; model mocked."""

import anthropic
import pytest
from helpers import HIGH, LOW
from langgraph.checkpoint.memory import InMemorySaver

from ticket_classifier.checkpoint import thread_config
from ticket_classifier.graph import build_workflow
from ticket_classifier.models import EscalatedTicket, ResolvedTicket
from ticket_classifier.runner import (
    NotPausedError,
    resume_ticket,
    run_all,
    run_ticket,
    to_classified_ticket,
)


@pytest.fixture
def workflow():
    return build_workflow(InMemorySaver())


def test_low_priority_ticket_is_handled_automatically(
    workflow_context, model, workflow, make_ticket
):
    result = run_ticket(
        workflow, workflow_context, make_ticket(id="T-1", customer_id="1001")
    )

    assert to_classified_ticket(result) == ResolvedTicket(
        ticket_id="T-1", customer_id="1001", category="billing", priority="low"
    )


def test_high_priority_ticket_pauses_for_a_human(
    workflow_context, model, workflow, make_ticket
):
    model.outcomes["urgent"] = HIGH

    assert (
        run_ticket(workflow, workflow_context, make_ticket(id="T-1", text="urgent"))
        is None
    )

    state = workflow.get_state(thread_config("T-1"))
    assert state.next == ("human_review",)
    request = state.interrupts[0].value
    assert request["ticket"].text == "urgent"
    assert request["customer"].first_name == "Alice"
    assert request["classification"] == HIGH


def test_paused_ticket_stays_paused_on_the_next_run(
    workflow_context, model, workflow, make_ticket
):
    model.outcomes["urgent"] = HIGH
    ticket = make_ticket(id="T-1", text="urgent")
    run_ticket(workflow, workflow_context, ticket)

    assert run_ticket(workflow, workflow_context, ticket) is None
    assert model.call_count == 1


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (
            {"approved": True, "note": "Dana takes it"},
            EscalatedTicket(
                ticket_id="T-1",
                customer_id="1001",
                category="billing",
                priority="high",
                escalation_reason="Dana takes it",
            ),
        ),
        (
            {"approved": False, "note": "Bot can answer"},
            ResolvedTicket(
                ticket_id="T-1", customer_id="1001", category="billing", priority="high"
            ),
        ),
    ],
)
def test_resume_finishes_with_the_answer(
    workflow_context, model, workflow, make_ticket, answer, expected
):
    model.outcomes["urgent"] = HIGH
    run_ticket(workflow, workflow_context, make_ticket(id="T-1", text="urgent"))

    result = resume_ticket(workflow, "T-1", answer)

    assert to_classified_ticket(result) == expected
    assert workflow.get_state(thread_config("T-1")).next == ()
    assert model.call_count == 1  # triage did not run again


def test_resume_without_paused_run_raises(model, workflow):
    with pytest.raises(NotPausedError, match="T-9"):
        resume_ticket(workflow, "T-9", {"approved": True, "note": ""})


def test_finished_ticket_returns_saved_result_without_running(
    workflow_context, model, workflow, make_ticket
):
    ticket = make_ticket(id="T-1")
    first = run_ticket(workflow, workflow_context, ticket)

    again = run_ticket(workflow, workflow_context, ticket)

    assert again == first
    assert model.call_count == 1


def test_crashed_run_continues_where_it_stopped(
    workflow_context, model, workflow, make_ticket
):
    model.outcomes["urgent"] = HIGH
    ticket = make_ticket(id="T-1", text="urgent")
    config = thread_config("T-1")
    # Stop the first run right after triage, before the last node starts.
    for values in workflow.stream(
        {"ticket": ticket}, config, context=workflow_context, stream_mode="values"
    ):
        if values.get("classification"):
            break
    assert workflow.get_state(config).next == ("human_review",)

    # Continued and paused.
    assert run_ticket(workflow, workflow_context, ticket) is None
    assert model.call_count == 1


def test_run_all_sorts_tickets_into_classified_paused_and_failed(
    workflow_context, model, workflow, make_ticket
):
    model.outcomes.update(
        {
            "urgent": HIGH,
            "refused": None,
            "api down": anthropic.APIError("down", request=None, body=None),
        }
    )
    tickets = [
        make_ticket(id="T-1"),
        make_ticket(id="T-2", text="urgent"),
        make_ticket(id="T-3", text="refused"),
        make_ticket(id="T-4", text="api down"),
    ]

    batch = run_all(tickets, workflow=workflow, context=workflow_context)

    assert [r.ticket_id for r in batch.classified] == ["T-1"]
    assert batch.paused == ["T-2"]
    assert batch.failed == ["T-3", "T-4"]


def test_failed_triage_is_retried_on_the_next_run(
    workflow_context, model, workflow, make_ticket
):
    model.outcomes["flaky"] = None
    ticket = make_ticket(id="T-1", text="flaky")
    assert run_all([ticket], workflow=workflow, context=workflow_context).failed == [
        "T-1"
    ]

    model.outcomes["flaky"] = LOW
    batch = run_all([ticket], workflow=workflow, context=workflow_context)

    assert [r.ticket_id for r in batch.classified] == ["T-1"]
