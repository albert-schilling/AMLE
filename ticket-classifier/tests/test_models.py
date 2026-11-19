import pytest
from pydantic import TypeAdapter, ValidationError

from ticket_classifier.models import (
    ClassifiedTicket,
    EscalatedTicket,
    ResolvedTicket,
    Ticket,
    TicketClassification,
)

RESULT = TypeAdapter(ClassifiedTicket)
FIELDS = {"ticket_id": "T-1", "category": "billing", "priority": "high"}


def test_classification_rejects_unknown_category():
    with pytest.raises(ValidationError):
        TicketClassification(category="spam", priority="low")


def test_classification_rejects_extra_fields():
    with pytest.raises(ValidationError):
        TicketClassification(category="billing", priority="low", reason="x")


def test_ticket_customer_id_is_optional():
    assert Ticket(id="T-1", text="x").customer_id is None


def test_result_union_picks_the_type_from_escalated():
    escalated = {**FIELDS, "escalated": True, "escalation_reason": "Dana"}

    resolved = {**FIELDS, "escalated": False}

    assert isinstance(RESULT.validate_python(escalated), EscalatedTicket)
    assert isinstance(RESULT.validate_python(resolved), ResolvedTicket)


@pytest.mark.parametrize(
    "row",
    [
        {**FIELDS, "escalated": True},  # escalated without a reason
        {
            **FIELDS,
            "escalated": False,
            "escalation_reason": "x",
        },  # reason, not escalated
        {"ticket_id": "T-1", "escalated": True, "escalation_reason": "x"},  # no class.
    ],
)
def test_impossible_results_are_rejected(row):
    with pytest.raises(ValidationError):
        RESULT.validate_python(row)
