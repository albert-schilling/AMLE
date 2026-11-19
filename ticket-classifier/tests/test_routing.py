import pytest

from ticket_classifier.models import TicketClassification
from ticket_classifier.nodes import route_after_triage
from ticket_classifier.nodes.names import HUMAN_REVIEW, MARK_HANDLED


def state_with(priority: str) -> dict:
    return {
        "classification": TicketClassification(category="billing", priority=priority)
    }


def test_high_priority_goes_to_a_human():
    assert route_after_triage(state_with("high")) == HUMAN_REVIEW


@pytest.mark.parametrize("priority", ["low", "medium"])
def test_other_priorities_are_handled_automatically(priority):
    assert route_after_triage(state_with(priority)) == MARK_HANDLED
