import anthropic

from ticket_classifier import ClassificationError
from ticket_classifier.batch import classify_all
from ticket_classifier.models import Customer, TicketClassification


def never(reason):
    return False


def final_state(customer=None, category="billing", priority="high"):
    return {
        "customer": customer,
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
    workflow = mocker.patch("ticket_classifier.batch.workflow")
    workflow.stream.side_effect = streams
    mocker.patch("ticket_classifier.batch.log_action")
    return workflow


def test_classify_all_collects_results(mocker, make_ticket):
    patch_workflow(mocker, final_state(), final_state(category="other"))

    batch = classify_all(
        [make_ticket(id="T-1"), make_ticket(customer_id=None, id="T-2")], never
    )

    assert [r.ticket_id for r in batch.classified] == ["T-1", "T-2"]
    assert [r.category for r in batch.classified] == ["billing", "other"]
    assert batch.failed == []


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
    patch_workflow(mocker, final_state(customer=customer))

    batch = classify_all([make_ticket()], never)

    assert batch.classified[0].customer_id == "1001"


def test_classify_all_skips_classification_errors(mocker, make_ticket):
    patch_workflow(mocker, ClassificationError("boom"), final_state())

    batch = classify_all([make_ticket(id="T-1"), make_ticket(id="T-2")], never)

    assert batch.failed == ["T-1"]
    assert [r.ticket_id for r in batch.classified] == ["T-2"]


def test_classify_all_skips_api_errors(mocker, make_ticket):
    patch_workflow(
        mocker,
        anthropic.APIError("down", request=mocker.Mock(), body=None),
        final_state(),
    )

    batch = classify_all([make_ticket(id="T-1"), make_ticket(id="T-2")], never)

    assert batch.failed == ["T-1"]
    assert [r.ticket_id for r in batch.classified] == ["T-2"]
