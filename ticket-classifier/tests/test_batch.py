import anthropic

from ticket_classifier import ClassificationError, TicketClassification
from ticket_classifier.batch import classify_all
from ticket_classifier.models import Escalated, Resolved

OK = Resolved(classification=TicketClassification(category="billing", priority="high"))


def never(reason):
    return False


def test_classify_all_collects_results(mocker, make_ticket, mock_client):
    mocker.patch("ticket_classifier.batch.classify", return_value=OK)

    batch = classify_all(
        [make_ticket(id="T-1"), make_ticket(customer_id=None, id="T-2")],
        mock_client,
        never,
    )

    assert [(r.ticket_id, r.customer_id) for r in batch.classified] == [
        ("T-1", "1001"),
        ("T-2", None),
    ]
    assert batch.failed == []


def test_classify_all_skips_classification_errors(mocker, make_ticket, mock_client):
    mocker.patch(
        "ticket_classifier.batch.classify",
        side_effect=[ClassificationError("boom"), OK],
    )

    batch = classify_all(
        [make_ticket(id="T-1"), make_ticket(id="T-2")], mock_client, never
    )

    assert batch.failed == ["T-1"]
    assert [r.ticket_id for r in batch.classified] == ["T-2"]


def test_classify_all_skips_api_errors(mocker, make_ticket, mock_client):
    mocker.patch(
        "ticket_classifier.batch.classify",
        side_effect=[anthropic.APIError("down", request=mocker.Mock(), body=None), OK],
    )

    batch = classify_all(
        [make_ticket(id="T-1"), make_ticket(id="T-2")], mock_client, never
    )

    assert batch.failed == ["T-1"]
    assert [r.ticket_id for r in batch.classified] == ["T-2"]


def test_classify_all_records_escalation(mocker, make_ticket, mock_client):
    escalated = Escalated(escalation_reason="cap")
    mocker.patch("ticket_classifier.batch.classify", return_value=escalated)

    batch = classify_all([make_ticket()], mock_client, never)

    assert batch.classified[0].escalated is True
    assert batch.classified[0].category is None
    assert batch.classified[0].escalation_reason == "cap"
