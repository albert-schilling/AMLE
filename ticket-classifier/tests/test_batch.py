import anthropic
from langgraph.types import Command

from ticket_classifier import ClassificationError
from ticket_classifier.batch import classify_all
from ticket_classifier.models import (
    Customer,
    Escalated,
    EscalatedTicket,
    NotEscalated,
    ResolvedTicket,
    TicketClassification,
)


def never(reason):
    return False


def final_state(customer=None, category="billing", priority="high", escalation=None):
    return {
        "customer": customer,
        "escalation": escalation or NotEscalated(),
        "classification": TicketClassification(category=category, priority=priority),
    }


def patch_workflow(mocker, *outcomes):
    """Each outcome is a final state, or an exception to raise for that ticket."""
    streams = []
    for outcome in outcomes:
        if isinstance(outcome, Exception):
            streams.append(outcome)
        else:
            streams.append(iter([("values", outcome)]))
    workflow = mocker.Mock()
    workflow.stream.side_effect = streams
    workflow.get_state.return_value.next = ()  # no unfinished run saved
    workflow.get_state.return_value.interrupts = ()  # no paused run saved
    mocker.patch("ticket_classifier.batch.log_action")
    return workflow


def test_classify_all_collects_results(mocker, make_ticket):
    workflow = patch_workflow(mocker, final_state(), final_state(category="other"))

    batch = classify_all(
        [make_ticket(id="T-1"), make_ticket(customer_id=None, id="T-2")],
        never,
        workflow=workflow,
    )

    assert [r.ticket_id for r in batch.classified] == ["T-1", "T-2"]
    assert [r.category for r in batch.classified] == ["billing", "other"]
    assert batch.failed == []


def test_classify_all_builds_escalated_ticket(mocker, make_ticket):
    escalation = Escalated(escalation_reason="High priority ticket")
    workflow = patch_workflow(mocker, final_state(escalation=escalation))

    batch = classify_all([make_ticket(id="T-1")], never, workflow=workflow)

    assert batch.classified == [
        EscalatedTicket(
            ticket_id="T-1",
            category="billing",
            priority="high",
            escalation_reason="High priority ticket",
        )
    ]


def test_classify_all_builds_resolved_ticket(mocker, make_ticket):
    workflow = patch_workflow(mocker, final_state(priority="low"))

    batch = classify_all([make_ticket(id="T-1")], never, workflow=workflow)

    assert batch.classified == [
        ResolvedTicket(ticket_id="T-1", category="billing", priority="low")
    ]


def test_classify_all_starts_a_new_run_with_the_ticket(mocker, make_ticket):
    workflow = patch_workflow(mocker, final_state())
    ticket = make_ticket(id="T-1")

    classify_all([ticket], never, workflow=workflow)

    args, kwargs = workflow.stream.call_args
    assert args[0] == {"ticket": ticket}
    assert args[1] == {"configurable": {"thread_id": "T-1"}}
    assert kwargs["durability"] == "sync"


def test_classify_all_resumes_an_unfinished_run_with_none(mocker, make_ticket):
    workflow = patch_workflow(mocker, final_state())
    workflow.get_state.return_value.next = ("node_wait_for_human",)

    classify_all([make_ticket(id="T-1")], never, workflow=workflow)

    assert workflow.stream.call_args.args[0] is None


def test_classify_all_resumes_a_paused_run_with_the_answer(mocker, make_ticket):
    workflow = patch_workflow(mocker, final_state())
    workflow.get_state.return_value.interrupts = (mocker.Mock(),)
    answer = {"approved": True, "note": "ok"}

    classify_all(
        [make_ticket(id="T-1")], never, workflow=workflow, answers={"T-1": answer}
    )

    run_input = workflow.stream.call_args.args[0]
    assert isinstance(run_input, Command)
    assert run_input.resume == answer


def test_classify_all_skips_a_paused_run_without_answer(mocker, make_ticket):
    workflow = patch_workflow(mocker)
    workflow.get_state.return_value.interrupts = (mocker.Mock(),)

    batch = classify_all([make_ticket(id="T-1")], never, workflow=workflow)

    assert batch.paused == ["T-1"]
    workflow.stream.assert_not_called()


def test_classify_all_records_a_run_that_pauses(mocker, make_ticket):
    workflow = patch_workflow(mocker)
    interrupt = mocker.Mock(value={"question": "?"})
    workflow.stream.side_effect = [
        iter([("values", final_state()), ("updates", {"__interrupt__": (interrupt,)})])
    ]

    batch = classify_all([make_ticket(id="T-1")], never, workflow=workflow)

    assert batch.paused == ["T-1"]
    assert batch.classified == []


def test_classify_all_takes_customer_id_from_state(mocker, make_ticket):
    customer = Customer(
        id="1001",
        first_name="Alice",
        last_name="Smith",
        email="alice@example.com",
        account_age_days=1,
        past_refunds_90d=0,
        plan="pro",
        products=[],
    )
    workflow = patch_workflow(mocker, final_state(customer=customer))

    batch = classify_all([make_ticket()], never, workflow=workflow)

    assert batch.classified[0].customer_id == "1001"


def test_classify_all_skips_classification_errors(mocker, make_ticket):
    workflow = patch_workflow(mocker, ClassificationError("boom"), final_state())

    batch = classify_all(
        [make_ticket(id="T-1"), make_ticket(id="T-2")], never, workflow=workflow
    )

    assert batch.failed == ["T-1"]
    assert [r.ticket_id for r in batch.classified] == ["T-2"]


def test_classify_all_skips_api_errors(mocker, make_ticket):
    workflow = patch_workflow(
        mocker,
        anthropic.APIError("down", request=mocker.Mock(), body=None),
        final_state(),
    )

    batch = classify_all(
        [make_ticket(id="T-1"), make_ticket(id="T-2")], never, workflow=workflow
    )

    assert batch.failed == ["T-1"]
    assert [r.ticket_id for r in batch.classified] == ["T-2"]
