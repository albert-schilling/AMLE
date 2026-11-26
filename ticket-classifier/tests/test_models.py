import pytest
from pydantic import TypeAdapter, ValidationError

from ticket_classifier.models import (
    ClassifiedTicket,
    EscalatedTicket,
    ResolvedTicket,
    Retrieval,
    RetrievalResult,
    TicketClassification,
)

RESULT = TypeAdapter(ClassifiedTicket)
REPLY = {"text": "Hi", "citations": []}
FIELDS = {
    "ticket_id": "T-1",
    "category": "billing",
    "priority": "high",
    "reply": REPLY,
}


def test_classification_rejects_extra_fields():
    with pytest.raises(ValidationError):
        TicketClassification(category="billing", priority="low", reason="x")


def test_result_union_picks_the_type_from_escalated():
    escalated = {**FIELDS, "escalated": True, "escalation_reason": "Dana"}
    resolved = {**FIELDS, "escalated": False}

    assert isinstance(RESULT.validate_python(escalated), EscalatedTicket)
    assert isinstance(RESULT.validate_python(resolved), ResolvedTicket)


NO_REASON = {**FIELDS, "escalated": True}
REASON_BUT_NOT_ESCALATED = {**FIELDS, "escalated": False, "escalation_reason": "x"}
NO_CLASSIFICATION = {
    "ticket_id": "T-1",
    "reply": REPLY,
    "escalated": True,
    "escalation_reason": "x",
}
NO_REPLY = {"ticket_id": "T-1", "category": "billing", "priority": "low"}


@pytest.mark.parametrize(
    "row", [NO_REASON, REASON_BUT_NOT_ESCALATED, NO_CLASSIFICATION, NO_REPLY]
)
def test_impossible_results_are_rejected(row):
    with pytest.raises(ValidationError):
        RESULT.validate_python(row)


RESULT_OF_A_SEARCH = RetrievalResult(passages=(), weak=(), min_score=0.65)


@pytest.mark.parametrize(
    "fields",
    [{"result": RESULT_OF_A_SEARCH}, {"queries": ("refund",), "ok": True}],
    ids=["result without query", "verdict without result"],
)
def test_search_steps_out_of_order_are_rejected(fields):
    with pytest.raises(ValidationError):
        Retrieval(**fields)


def test_next_query_clears_the_result_and_verdict_of_the_previous_one():
    judged = (
        Retrieval(queries=("refund",)).with_result(RESULT_OF_A_SEARCH).judged(False)
    )

    assert judged.with_query("refund policy") == Retrieval(
        queries=("refund", "refund policy")
    )
