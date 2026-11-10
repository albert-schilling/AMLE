import pytest
from pydantic import ValidationError

from ticket_classifier import Ticket, TicketClassification


def test_classification_rejects_unknown_category():
    with pytest.raises(ValidationError):
        TicketClassification(category="spam", priority="low")


def test_ticket_customer_id_is_optional():
    assert Ticket(id="T-1", text="x").customer_id is None
