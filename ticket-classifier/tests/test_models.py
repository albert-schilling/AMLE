import pytest
from pydantic import TypeAdapter, ValidationError

from ticket_classifier.models import (
    ClassifiedTicket,
    EscalatedTicket,
    ResolvedTicket,
    TicketClassification,
)

RESULT = TypeAdapter(ClassifiedTicket)
FIELDS = {"ticket_id": "T-1", "category": "billing", "priority": "high"}


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
NO_CLASSIFICATION = {"ticket_id": "T-1", "escalated": True, "escalation_reason": "x"}


@pytest.mark.parametrize(
    "row", [NO_REASON, REASON_BUT_NOT_ESCALATED, NO_CLASSIFICATION]
)
def test_impossible_results_are_rejected(row):
    with pytest.raises(ValidationError):
        RESULT.validate_python(row)
